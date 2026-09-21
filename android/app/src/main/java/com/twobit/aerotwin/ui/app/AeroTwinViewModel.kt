package com.twobit.aerotwin.ui.app

import android.app.Application
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import android.os.SystemClock
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.twobit.aerotwin.core.config.BaseUrlStore
import com.twobit.aerotwin.core.config.SessionStore
import com.twobit.aerotwin.core.config.SensorDeviceStore
import com.twobit.aerotwin.core.config.StoredSensorDevice
import com.twobit.aerotwin.data.api.AeroTwinApiFactory
import com.twobit.aerotwin.data.api.ErrorBody
import com.twobit.aerotwin.data.api.InspectionCreateRequest
import com.twobit.aerotwin.data.api.InspectionDto
import com.twobit.aerotwin.data.api.LoginRequest
import com.twobit.aerotwin.data.api.ReadingCreateRequest
import com.twobit.aerotwin.data.api.ReadingDto
import com.twobit.aerotwin.data.api.ReviewExceptionDto
import com.twobit.aerotwin.data.api.EmptyConfirmationRequest
import com.twobit.aerotwin.data.api.UserDto
import com.twobit.aerotwin.data.api.ZoneDto
import com.twobit.aerotwin.data.api.SensorMissionDto
import com.twobit.aerotwin.data.api.SensorNextObjectiveDto
import com.twobit.aerotwin.data.api.SensorRegisterRequest
import com.twobit.aerotwin.data.api.SensorStatusDto
import com.twobit.aerotwin.data.api.SensorTelemetryRequest
import com.twobit.aerotwin.data.api.DashboardDto
import com.twobit.aerotwin.data.api.ExceptionSummaryDto
import com.twobit.aerotwin.data.api.ExceptionDetailDto
import com.twobit.aerotwin.data.api.FlowTwinDto
import com.twobit.aerotwin.data.api.AgentRequest
import com.twobit.aerotwin.data.api.AgentResponseDto
import com.twobit.aerotwin.data.api.LiveInspectionStateDto
import com.twobit.aerotwin.core.sensor.CaptureQuality
import com.twobit.aerotwin.core.sensor.SensorPhase
import com.twobit.aerotwin.core.sensor.SensorBox
import com.twobit.aerotwin.core.sensor.SensorQrCode
import com.twobit.aerotwin.core.sensor.SensorUiState
import com.twobit.aerotwin.core.sensor.SensorDetection
import com.twobit.aerotwin.core.sensor.DetectionTone
import com.twobit.aerotwin.core.sensor.StabilityTracker
import com.twobit.aerotwin.core.sensor.STABLE_FRAMES_REQUIRED
import com.twobit.aerotwin.core.sensor.calculateCaptureQuality
import com.twobit.aerotwin.core.sensor.parseSensorQr
import com.twobit.aerotwin.data.api.HealthApiFactory
import com.twobit.aerotwin.ui.sensor.CameraBarcodeDetection
import java.io.IOException
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.UUID
import kotlinx.coroutines.launch
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.coroutines.CancellationException
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.HttpException

enum class AppScreen { CONNECTION, MODE_SELECTION, LOGIN, HOME, TWIN, ZONE_SELECTION, INSPECTION, READING, SENSOR_PAIRING, SENSOR_WAITING, SENSOR, DRONE_MONITOR, SUPERVISOR_EXCEPTIONS, EXCEPTIONS, EXCEPTION_DETAIL, FLOWTWIN_CHANGES, AGENT, LOCATION_HISTORY, EVIDENCE }

/** Parameters owned by Core and applied to the operational exception list. */
data class ExceptionFilters(
    val type: String? = null,
    val severity: String? = null,
    val zone: String? = null,
    val expiry: Boolean = false,
    val lot: String? = null,
    val qualityMax: Int? = null,
)

data class AppUiState(
    val screen: AppScreen = AppScreen.CONNECTION,
    val loading: Boolean = false,
    val error: String? = null,
    val connectionMessage: String? = null,
    val coreConnected: Boolean = false,
    val user: UserDto? = null,
    val zones: List<ZoneDto> = emptyList(),
    val inspection: InspectionDto? = null,
    val result: ReadingDto? = null,
    val lastReading: ReadingDto? = null,
    val sensorMission: SensorMissionDto? = null,
    val droneStatus: SensorStatusDto? = null,
    val droneFrame: Bitmap? = null,
    val drones: List<SensorStatusDto> = emptyList(),
    val liveFrames: Map<Int, Bitmap> = emptyMap(),
    val selectedDroneId: Int? = null,
    val reviewExceptions: List<ReviewExceptionDto> = emptyList(),
    val reviewEvidence: Map<Int, Bitmap> = emptyMap(),
    val dashboard: DashboardDto? = null,
    /** Lightweight physical projection of the active inspection, refreshed only on live surfaces. */
    val liveState: LiveInspectionStateDto? = null,
    /** Increments when Core changes the live projection; cells use it for a restrained transition. */
    val liveStateRevision: Long = 0L,
    val exceptions: List<ExceptionSummaryDto> = emptyList(),
    val exceptionFilters: ExceptionFilters = ExceptionFilters(),
    val exceptionDetail: ExceptionDetailDto? = null,
    val exceptionDetailOrigin: AppScreen = AppScreen.EXCEPTIONS,
    val flowTwin: FlowTwinDto? = null,
    val agentResponse: AgentResponseDto? = null,
    val locationMemory: com.google.gson.JsonObject? = null,
    val recurrentLocations: List<com.google.gson.JsonObject> = emptyList(),
    val locationHistoryOrigin: AppScreen = AppScreen.HOME,
    val agentEvidence: Bitmap? = null,
    val agentEvidenceId: Int? = null,
    val evidenceOrigin: AppScreen = AppScreen.AGENT,
)

data class PreparedEvidence(
    val preview: Bitmap,
    val jpegBytes: ByteArray,
)

class AeroTwinViewModel(application: Application) : AndroidViewModel(application) {
    private val baseUrlStore = BaseUrlStore(application)
    private val sessionStore = SessionStore(application)
    private val sensorDeviceStore = SensorDeviceStore(application)

    var baseUrl by mutableStateOf(baseUrlStore.load())
        private set
    var username by mutableStateOf("operator01")
        private set
    var password by mutableStateOf("")
        private set
    var locationCode by mutableStateOf("")
        private set
    var palletCode by mutableStateOf("")
        private set
    var qualityScore by mutableStateOf("95")
        private set
    var observedState by mutableStateOf("PALLET")
    var evidence by mutableStateOf<PreparedEvidence?>(null)
    var sensorUiState by mutableStateOf(SensorUiState())
        private set
    /** The Core-owned next target displayed by the sensor; it is never selected locally. */
    var sensorObjective by mutableStateOf<SensorNextObjectiveDto?>(null)
        private set
    var sensorName by mutableStateOf(sensorDeviceStore.load()?.name ?: "Sensor 01")
        private set
    var showServerConfiguration by mutableStateOf(baseUrl.isBlank())
        private set
    var uiState by mutableStateOf(AppUiState())
        private set

    private var token: String = sessionStore.loadToken()
    private var sensorDevice: StoredSensorDevice? = sensorDeviceStore.load()
    private var sensorMissionPollingJob: Job? = null
    private var droneMonitorJob: Job? = null
    private var liveStatePollingJob: Job? = null
    private var appInForeground = true
    private var previewUploadBusy = false
    private val completedSensorLocations = mutableSetOf<String>()
    var analyzerStatus by mutableStateOf("Iniciando visión…")
        private set
    var liveStatus by mutableStateOf("Preparando transmisión…")
        private set
    var objectDetections by mutableStateOf<List<SensorDetection>>(emptyList())
        private set
    private var readingGroupId: String = UUID.randomUUID().toString()
    private var attemptNumber: Int = 1
    private var clientReadingId: String = UUID.randomUUID().toString()
    private var sensorLocationId: Int? = null
    private var sensorUnresolvedPending = false
    private var lastReportedSensorCode: String? = null
    private val locationStability = StabilityTracker()
    private val palletStability = StabilityTracker()
    /** Timestamp (elapsedRealtime) when SEARCHING_PALLET phase started. */
    private var palletSearchStartedAt: Long = 0L

    companion object {
        /** Time budget per autonomous observation before reporting UNRESOLVED. */
        const val PALLET_SEARCH_TIMEOUT_MS = 30_000L
        /** Match Core acceptance: don't upload a low-quality capture as a valid reading. */
        const val MIN_AUTO_CAPTURE_QUALITY = 85
    }

    init {
        if (baseUrl.isNotBlank()) testConnection()
    }

    /**
     * The digital twin deliberately polls only while an operator is actively
     * looking at a live operational surface.  There is no background polling,
     * WebSocket, or analytics fan-out hidden behind this MVP behavior.
     */
    fun setAppInForeground(inForeground: Boolean) {
        appInForeground = inForeground
        updateLiveStatePolling()
    }

    private fun isLiveInspectionScreen(screen: AppScreen = uiState.screen): Boolean =
        screen == AppScreen.HOME || screen == AppScreen.TWIN || screen == AppScreen.DRONE_MONITOR

    private fun isActiveInspection(inspection: InspectionDto? = uiState.inspection): Boolean =
        inspection?.status == "IN_PROGRESS"

    private fun updateLiveStatePolling() {
        val inspection = uiState.inspection
        val inspectionId = inspection?.id
        val allowed = appInForeground && token.isNotBlank() && inspectionId != null &&
            isActiveInspection(inspection) && isLiveInspectionScreen()
        if (!allowed) {
            liveStatePollingJob?.cancel()
            liveStatePollingJob = null
            return
        }
        if (liveStatePollingJob?.isActive == true) return
        liveStatePollingJob = viewModelScope.launch {
            while (
                appInForeground && isLiveInspectionScreen() &&
                    uiState.inspection?.id == inspectionId && isActiveInspection()
            ) {
                refreshLiveState(inspectionId, reportFailure = false)
                delay(900)
            }
        }
    }

    /** A manual/screen-entry refresh; polling failures remain silent so a stale frame does not erase the twin. */
    fun refreshLiveStateNow() {
        val inspectionId = uiState.inspection?.takeIf { isActiveInspection(it) }?.id ?: return
        viewModelScope.launch { refreshLiveState(inspectionId, reportFailure = true) }
    }

    private suspend fun refreshLiveState(inspectionId: Int, reportFailure: Boolean) {
        runCatching { AeroTwinApiFactory.create(baseUrl, token).inspectionLiveState(inspectionId) }
            .onSuccess { live ->
                // A delayed response from an old inspection must never repaint the current twin.
                if (uiState.inspection?.id != inspectionId) return@onSuccess
                val previous = uiState.liveState
                val currentInspection = uiState.inspection ?: return@onSuccess
                val updatedInspection = currentInspection.copy(
                    zoneCode = live.zone ?: currentInspection.zoneCode,
                    totalLocations = live.total,
                    completedLocations = live.inspected,
                )
                uiState = uiState.copy(
                    inspection = updatedInspection,
                    liveState = live,
                    liveStateRevision = if (previous != live) uiState.liveStateRevision + 1 else uiState.liveStateRevision,
                    error = if (reportFailure) null else uiState.error,
                )
            }
            .onFailure { failure ->
                // An inspection can be completed by another station between polls.  Do
                // not keep a request loop alive merely because the old projection is
                // still cached locally.
                if (failure is HttpException && failure.code() in setOf(404, 409)) {
                    val active = runCatching { AeroTwinApiFactory.create(baseUrl, token).activeInspection() }.getOrNull()
                    if (active == null || active.id != inspectionId) {
                        uiState = uiState.copy(inspection = active, liveState = null)
                        updateLiveStatePolling()
                        return@onFailure
                    }
                }
                if (reportFailure && isLiveInspectionScreen() && uiState.inspection?.id == inspectionId) {
                    uiState = uiState.copy(error = apiMessage(failure))
                } else {
                    Log.w("AeroTwinLive", "Live-state refresh deferred", failure)
                }
            }
    }

    fun onBaseUrlChanged(value: String) {
        baseUrl = value
        uiState = uiState.copy(error = null, connectionMessage = null)
    }

    fun showServerConfiguration() {
        showServerConfiguration = true
        uiState = uiState.copy(error = null)
    }

    fun onUsernameChanged(value: String) { username = value }
    fun onPasswordChanged(value: String) { password = value }
    fun onSensorNameChanged(value: String) { sensorName = value.take(120) }
    fun onLocationChanged(value: String) { locationCode = value.uppercase() }
    fun onPalletChanged(value: String) { palletCode = value.uppercase() }
    fun onQualityChanged(value: String) { qualityScore = value.filter(Char::isDigit).take(3) }
    fun onObservedStateChanged(value: String) {
        observedState = value
        if (value != "PALLET") palletCode = ""
    }

    fun selectEvidence(uri: Uri?) {
        if (uri == null || uiState.loading) return
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching { withContext(Dispatchers.IO) { prepareEvidence(uri) } }
                .onSuccess { prepared ->
                    evidence = prepared
                    uiState = uiState.copy(loading = false)
                }
                .onFailure {
                    uiState = uiState.copy(
                        loading = false,
                        error = "No pudimos procesar esta imagen. Prueba con otra fotografía.",
                    )
                }
        }
    }

    fun clearEvidence() { evidence = null }

    fun testConnection() {
        if (uiState.loading) return
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null, connectionMessage = null)
            runCatching {
                val normalized = HealthApiFactory.normalizeBaseUrl(baseUrl)
                val health = AeroTwinApiFactory.create(normalized).health()
                require(health.status.equals("ok", ignoreCase = true))
                normalized
            }.onSuccess { normalized ->
                baseUrl = normalized
                baseUrlStore.save(normalized)
                showServerConfiguration = false
                uiState = AppUiState(
                    screen = AppScreen.MODE_SELECTION,
                    connectionMessage = "AeroTwin Core conectado",
                    coreConnected = true,
                )
            }.onFailure {
                uiState = uiState.copy(
                    loading = false,
                    error = "No pudimos conectar. Verifica el backend y la red local.",
                )
            }
        }
    }

    fun chooseOperatorMode() {
        viewModelScope.launch { restoreOperatorSessionOrShowLogin() }
    }

    fun chooseSensorMode() {
        val device = sensorDevice
        if (device == null) {
            // A prototype drone is a device identity, not a human user. Pair it
            // transparently the first time so entering Sensor Mode is one action.
            registerSensorAutomatically()
        } else {
            activateSensorMode()
        }
    }

    fun backToModeSelection() {
        sensorMissionPollingJob?.cancel()
        uiState = uiState.copy(screen = AppScreen.MODE_SELECTION, loading = false, error = null)
    }

    private fun activateSensorMode() {
        uiState = uiState.copy(screen = AppScreen.SENSOR_WAITING, loading = false, error = null)
        startSensorMissionPolling()
    }

    private fun registerSensorAutomatically() {
        val name = sensorName.trim().ifBlank { "Dron móvil" }
        val normalizedBaseUrl = HealthApiFactory.normalizeBaseUrl(baseUrl)
        baseUrl = normalizedBaseUrl
        baseUrlStore.save(normalizedBaseUrl)
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching { AeroTwinApiFactory.create(baseUrl).registerSensor(SensorRegisterRequest(name)) }
                .onSuccess { registered ->
                    sensorDevice = StoredSensorDevice(registered.id, registered.deviceCode, registered.name, registered.deviceToken)
                    sensorDeviceStore.save(sensorDevice!!)
                    sensorName = registered.name
                    activateSensorMode()
                }
                .onFailure { uiState = uiState.copy(loading = false, error = apiMessage(it)) }
        }
    }

    private suspend fun restoreOperatorSessionOrShowLogin() {
        if (token.isBlank()) {
            uiState = AppUiState(
                screen = AppScreen.LOGIN,
                connectionMessage = "AeroTwin Core conectado",
                coreConnected = true,
            )
            return
        }
        runCatching { AeroTwinApiFactory.create(baseUrl, token).me() }
            .onSuccess { user ->
                uiState = AppUiState(
                    screen = AppScreen.HOME,
                    user = user,
                    coreConnected = true,
                )
                loadHome()
            }
            .onFailure {
                sessionStore.clear()
                token = ""
                uiState = AppUiState(screen = AppScreen.LOGIN)
            }
    }

    fun pairSensor() {
        val name = sensorName.trim()
        if (name.length < 2) {
            uiState = uiState.copy(error = "Ingresa un nombre para el sensor.")
            return
        }
        val normalizedBaseUrl = HealthApiFactory.normalizeBaseUrl(baseUrl)
        baseUrl = normalizedBaseUrl
        baseUrlStore.save(normalizedBaseUrl)
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching { AeroTwinApiFactory.create(baseUrl).registerSensor(SensorRegisterRequest(name)) }
                .onSuccess { registered ->
                    sensorDevice = StoredSensorDevice(registered.id, registered.deviceCode, registered.name, registered.deviceToken)
                    sensorDeviceStore.save(sensorDevice!!)
                    sensorName = registered.name
                    uiState = uiState.copy(loading = false, error = null)
                    activateSensorMode()
                }
                .onFailure { uiState = uiState.copy(loading = false, error = apiMessage(it)) }
        }
    }

    fun refreshSensorMission() {
        if (uiState.loading) return
        val device = sensorDevice ?: return
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                val response = AeroTwinApiFactory.createSensor(baseUrl, device.token).sensorMission()
                if (!response.isSuccessful) throw HttpException(response)
                response.body()
            }
                .onSuccess { mission ->
                    if (mission == null) {
                        uiState = uiState.copy(screen = AppScreen.SENSOR_WAITING, loading = false, sensorMission = null)
                    } else {
                        startDeviceMission(mission)
                    }
                }
                .onFailure { failure ->
                    // A demo reset removes device tokens. Recover by pairing this phone again,
                    // rather than leaving the sensor stuck in an unauthenticated waiting state.
                    if (failure is HttpException && failure.code() in setOf(401, 404)) {
                        sensorMissionPollingJob?.cancel()
                        sensorDeviceStore.clear()
                        sensorDevice = null
                        sensorName = device.name
                        uiState = uiState.copy(loading = false, error = null)
                        registerSensorAutomatically()
                    } else {
                        uiState = uiState.copy(loading = false, error = apiMessage(failure))
                    }
                }
        }
    }

    private fun startSensorMissionPolling() {
        sensorMissionPollingJob?.cancel()
        sensorMissionPollingJob = viewModelScope.launch {
            while (uiState.screen == AppScreen.SENSOR_WAITING) {
                refreshSensorMission()
                delay(4_000)
            }
        }
    }

    private fun startDeviceMission(mission: SensorMissionDto) {
        sensorMissionPollingJob?.cancel()
        locationStability.reset()
        palletStability.reset()
        sensorLocationId = null
        sensorUnresolvedPending = false
        lastReportedSensorCode = null
        sensorObjective = null
        if (uiState.sensorMission?.inspectionId != mission.inspectionId) completedSensorLocations.clear()
        nextReading()
        sensorUiState = SensorUiState(message = "Buscando etiquetas…")
        uiState = uiState.copy(
            screen = AppScreen.SENSOR,
            loading = false,
            inspection = InspectionDto(mission.inspectionId, 0, mission.zone, mission.status, "", 0, 0),
            sensorMission = mission,
            result = null,
            error = null,
        )
        refreshSensorObjective()
    }

    fun login() {
        if (uiState.loading) return
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                AeroTwinApiFactory.create(baseUrl).login(
                    LoginRequest(username.trim(), password)
                )
            }.onSuccess { response ->
                token = response.accessToken
                sessionStore.saveToken(token)
                password = ""
                uiState = AppUiState(
                    screen = AppScreen.HOME,
                    user = response.user,
                    coreConnected = true,
                )
                loadHome()
            }.onFailure { error ->
                uiState = uiState.copy(loading = false, error = apiMessage(error))
            }
        }
    }

    fun loadHome() {
        if (token.isBlank()) return
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                val api = AeroTwinApiFactory.create(baseUrl, token)
                api.dashboard() to api.activeInspection()
            }.onSuccess { (dashboard, inspection) ->
                uiState = uiState.copy(
                    screen = AppScreen.HOME,
                    loading = false,
                    inspection = inspection,
                    dashboard = dashboard,
                    liveState = uiState.liveState?.takeIf { it.inspectionId == inspection?.id },
                )
                loadFlowTwinSummary()
                loadRecurrentLocations()
                updateLiveStatePolling()
            }.onFailure { handleAuthenticatedFailure(it) }
        }
    }

    /** Opens the spatial, live projection rather than adding more content to Home. */
    fun openTwin() {
        val existing = uiState.inspection
        if (existing != null) {
            uiState = uiState.copy(screen = AppScreen.TWIN, error = null)
            updateLiveStatePolling()
            refreshLiveStateNow()
            return
        }
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching { AeroTwinApiFactory.create(baseUrl, token).activeInspection() }
                .onSuccess { inspection ->
                    if (inspection == null) {
                        uiState = uiState.copy(screen = AppScreen.HOME, loading = false, error = "No hay una inspección activa para mostrar en el gemelo.")
                    } else {
                        uiState = uiState.copy(screen = AppScreen.TWIN, loading = false, inspection = inspection, liveState = null)
                        updateLiveStatePolling()
                        refreshLiveStateNow()
                    }
                }
                .onFailure { handleAuthenticatedFailure(it) }
        }
    }

    private fun loadFlowTwinSummary() {
        viewModelScope.launch {
            runCatching { AeroTwinApiFactory.create(baseUrl, token).flowTwinChanges() }
                .onSuccess { uiState = uiState.copy(flowTwin = it) }
        }
    }
    private fun loadRecurrentLocations() { viewModelScope.launch { runCatching { AeroTwinApiFactory.create(baseUrl,token).memoryLocations() }.onSuccess { response -> uiState=uiState.copy(recurrentLocations=response.getAsJsonArray("items").map { it.asJsonObject }.filter { it.get("consecutive_anomalous_inspections").asInt>=2 }.take(3)) } } }

    fun openExceptions(
        type: String? = null,
        severity: String? = null,
        zone: String? = null,
        expiry: Boolean = false,
        lot: String? = null,
        qualityMax: Int? = null,
    ) {
        liveStatePollingJob?.cancel()
        liveStatePollingJob = null
        val filters = ExceptionFilters(
            type = type?.trim()?.ifBlank { null },
            severity = severity?.trim()?.ifBlank { null },
            zone = zone?.trim()?.ifBlank { null },
            expiry = expiry,
            lot = lot?.trim()?.ifBlank { null },
            qualityMax = qualityMax?.coerceIn(0, 100),
        )
        viewModelScope.launch {
            uiState = uiState.copy(
                loading = true,
                error = null,
                screen = AppScreen.EXCEPTIONS,
                exceptionFilters = filters,
            )
            runCatching {
                AeroTwinApiFactory.create(baseUrl, token).exceptions(
                    type = filters.type,
                    severity = filters.severity,
                    zone = filters.zone,
                    expiry = filters.expiry.takeIf { it },
                    lot = filters.lot,
                    qualityMax = filters.qualityMax,
                )
            }
                .onSuccess { uiState = uiState.copy(loading = false, exceptions = it.items) }
                .onFailure { handleAuthenticatedFailure(it) }
        }
    }

    fun openExceptionDetail(id: Int) {
        val origin = uiState.screen
        liveStatePollingJob?.cancel()
        liveStatePollingJob = null
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null, screen = AppScreen.EXCEPTION_DETAIL, exceptionDetailOrigin = origin)
            runCatching { AeroTwinApiFactory.create(baseUrl, token).exceptionDetail(id) }
                .onSuccess { uiState = uiState.copy(loading = false, exceptionDetail = it) }
                .onFailure { handleAuthenticatedFailure(it) }
        }
    }

    fun backToExceptions() { uiState = uiState.copy(screen = AppScreen.EXCEPTIONS, error = null) }

    fun backFromExceptionDetail() {
        val origin = uiState.exceptionDetailOrigin
        uiState = uiState.copy(screen = origin, error = null)
        updateLiveStatePolling()
    }

    fun openFlowTwinChanges() {
        viewModelScope.launch {
            uiState = uiState.copy(screen = AppScreen.FLOWTWIN_CHANGES, loading = true, error = null)
            runCatching { AeroTwinApiFactory.create(baseUrl, token).flowTwinChanges() }
                .onSuccess { uiState = uiState.copy(loading = false, flowTwin = it) }
                .onFailure { handleAuthenticatedFailure(it) }
        }
    }
    fun openAgent() {
        liveStatePollingJob?.cancel()
        liveStatePollingJob = null
        uiState = uiState.copy(screen = AppScreen.AGENT, error = null, agentResponse = null)
    }
    fun askAgent(question: String) {
        if (question.isBlank()) return
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching { AeroTwinApiFactory.create(baseUrl, token).agentQuery(AgentRequest(question)) }
                .onSuccess { uiState = uiState.copy(loading = false, agentResponse = it) }
                .onFailure { handleAuthenticatedFailure(it) }
        }
    }
    fun openLocationHistory(id: Int) {
        val origin = uiState.screen
        viewModelScope.launch {
            uiState = uiState.copy(
                screen = AppScreen.LOCATION_HISTORY,
                locationHistoryOrigin = origin,
                loading = true,
                error = null,
                locationMemory = null,
            )
            runCatching { AeroTwinApiFactory.create(baseUrl, token).locationMemory(id) }
                .onSuccess { uiState = uiState.copy(loading = false, locationMemory = it) }
                .onFailure { handleAuthenticatedFailure(it) }
        }
    }

    fun backFromLocationHistory() {
        val destination = uiState.locationHistoryOrigin
        uiState = uiState.copy(screen = destination, error = null)
    }

    /** Opens a read-only evidence asset referenced by an Agent response. */
    fun openEvidence(evidenceId: Int) {
        val origin = uiState.screen
        viewModelScope.launch {
            uiState = uiState.copy(
                screen = AppScreen.EVIDENCE,
                evidenceOrigin = origin,
                agentEvidenceId = evidenceId,
                agentEvidence = null,
                loading = true,
                error = null,
            )
            runCatching {
                withContext(Dispatchers.IO) {
                    AeroTwinApiFactory.create(baseUrl, token)
                        .evidence(evidenceId)
                        .byteStream()
                        .use(BitmapFactory::decodeStream)
                        ?: throw IOException("La evidencia no contiene una imagen válida.")
                }
            }.onSuccess { frame ->
                uiState = uiState.copy(loading = false, agentEvidence = frame)
            }.onFailure { handleAuthenticatedFailure(it) }
        }
    }

    fun backFromEvidence() {
        uiState = uiState.copy(screen = uiState.evidenceOrigin, error = null)
    }

    /**
     * An Agent may request the live monitor without assuming that the Home screen
     * already has an active inspection cached. The monitor remains read-only.
     */
    fun openSensorMonitorFromAgent() {
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching { AeroTwinApiFactory.create(baseUrl, token).activeInspection() }
                .onSuccess { inspection ->
                    if (inspection == null) {
                        uiState = uiState.copy(
                            screen = AppScreen.AGENT,
                            loading = false,
                            error = "No existe una inspección activa para monitorear sensores.",
                        )
                    } else {
                        uiState = uiState.copy(inspection = inspection, loading = false, error = null)
                        monitorDrone()
                    }
                }
                .onFailure { handleAuthenticatedFailure(it) }
        }
    }

    fun openZoneSelection() {
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching { AeroTwinApiFactory.create(baseUrl, token).zones() }
                .onSuccess { zones ->
                    uiState = uiState.copy(
                        screen = AppScreen.ZONE_SELECTION,
                        loading = false,
                        zones = zones,
                    )
                }
                .onFailure { handleAuthenticatedFailure(it) }
        }
    }

    fun createInspection(zone: ZoneDto) {
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                AeroTwinApiFactory.create(baseUrl, token)
                    .createInspection(InspectionCreateRequest(zone.id))
            }.onSuccess { inspection ->
                uiState = uiState.copy(
                    screen = AppScreen.INSPECTION,
                    loading = false,
                    inspection = inspection,
                    error = null,
                )
            }.onFailure { handleAuthenticatedFailure(it) }
        }
    }

    fun openInspection() {
        uiState.inspection?.let {
            uiState = uiState.copy(screen = AppScreen.INSPECTION, error = null)
        }
    }

    fun monitorDrone() {
        if (uiState.inspection == null) return
        uiState = uiState.copy(screen = AppScreen.DRONE_MONITOR, error = null)
        updateLiveStatePolling()
        droneMonitorJob?.cancel()
        droneMonitorJob = viewModelScope.launch {
            while (uiState.screen == AppScreen.DRONE_MONITOR) {
                updateDroneViews()
                delay(600)
            }
        }
    }

    fun refreshDroneMonitor() {
        monitorDrone()
    }

    private suspend fun updateDroneViews() {
        try {
            val api = AeroTwinApiFactory.create(baseUrl, token)
            val drones = api.sensors().filter {
                it.mission?.inspectionId == uiState.inspection?.id && it.status == "ONLINE"
            }
            val selected = uiState.selectedDroneId?.takeIf { selectedId -> drones.any { it.id == selectedId } }
                ?: drones.firstOrNull()?.id
            // A monitor owns a single selected feed, never a polling mosaic.
            val frames = selected?.let { sensorId ->
                withContext(Dispatchers.IO) {
                    try {
                        val response = api.livePreview(sensorId)
                        val bitmap = response.body()?.use { body -> body.byteStream().use(BitmapFactory::decodeStream) }
                        if (response.isSuccessful && bitmap != null) mapOf(sensorId to bitmap) else emptyMap()
                    } catch (e: CancellationException) { throw e }
                    catch (_: Exception) { emptyMap() }
                }
            } ?: emptyMap()
            if (uiState.screen == AppScreen.DRONE_MONITOR) {
                uiState = uiState.copy(loading = false, drones = drones, liveFrames = frames, selectedDroneId = selected, error = null)
            }
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) {
            uiState = uiState.copy(loading = false, liveFrames = emptyMap(), error = apiMessage(e))
        }
    }

    fun backToInspectionFromMonitor() {
        droneMonitorJob?.cancel()
        liveStatePollingJob?.cancel()
        liveStatePollingJob = null
        uiState = uiState.copy(screen = AppScreen.INSPECTION, drones = emptyList(), liveFrames = emptyMap(), selectedDroneId = null, error = null)
        // Inspection is a non-live configuration screen; Home/Twin own the live projection.
    }

    fun onAnalyzerStatus(message: String) { analyzerStatus = message }
    fun onObjectDetections(objects: List<SensorDetection>) { objectDetections = objects }
    fun uploadLiveFrame(jpeg: ByteArray) {
        val device = sensorDevice ?: return
        if (previewUploadBusy || uiState.screen != AppScreen.SENSOR || uiState.sensorMission == null) return
        previewUploadBusy = true
        viewModelScope.launch {
            try {
                val part = MultipartBody.Part.createFormData("frame", "live.jpg", jpeg.toRequestBody("image/jpeg".toMediaType()))
                val response = AeroTwinApiFactory.createSensor(baseUrl, device.token).uploadPreview(part)
                if (!response.isSuccessful) throw HttpException(response)
                liveStatus = "Transmitiendo a Control · 0.2.0"
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { liveStatus = "Transmisión: ${apiMessage(e)}" }
            finally { previewUploadBusy = false }
        }
    }

    fun startManualReading() {
        uiState.inspection?.let(::prepareReading)
    }

    private fun reportSensorQrDetected(code: String) {
        if (code == lastReportedSensorCode || uiState.sensorMission == null) return
        lastReportedSensorCode = code
        val device = sensorDevice ?: return
        viewModelScope.launch {
            runCatching {
                AeroTwinApiFactory.createSensor(baseUrl, device.token).uploadTelemetry(
                    SensorTelemetryRequest(message = "QR detectado", detectedCode = code),
                )
            }
        }
    }

    fun selectDrone(sensorId: Int) {
        if (uiState.drones.any { it.id == sensorId }) uiState = uiState.copy(selectedDroneId = sensorId)
    }

    fun openReviewExceptions() {
        val inspection = uiState.inspection ?: return
        if (uiState.user?.role != "SUPERVISOR") return
        uiState = uiState.copy(screen = AppScreen.SUPERVISOR_EXCEPTIONS, loading = true, error = null)
        viewModelScope.launch {
            runCatching { AeroTwinApiFactory.create(baseUrl, token).reviewExceptions(inspection.id) }
                .onSuccess {
                    uiState = uiState.copy(loading = false, reviewExceptions = it, reviewEvidence = emptyMap())
                    it.flatMap { exception -> exception.evidenceAttempts }.forEach { evidence -> loadReviewEvidence(evidence.evidenceId) }
                }
                .onFailure { handleAuthenticatedFailure(it) }
        }
    }

    private fun loadReviewEvidence(evidenceId: Int) {
        viewModelScope.launch {
            val bitmap = runCatching {
                withContext(Dispatchers.IO) {
                    AeroTwinApiFactory.create(baseUrl, token).evidence(evidenceId).byteStream().use(BitmapFactory::decodeStream)
                }
            }.getOrNull() ?: return@launch
            uiState = uiState.copy(reviewEvidence = uiState.reviewEvidence + (evidenceId to bitmap))
        }
    }

    fun confirmExceptionEmpty(readingGroupId: String) {
        val inspection = uiState.inspection ?: return
        if (uiState.user?.role != "SUPERVISOR") return
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                AeroTwinApiFactory.create(baseUrl, token).confirmExceptionEmpty(
                    inspection.id, EmptyConfirmationRequest(readingGroupId),
                )
            }.onSuccess {
                uiState = uiState.copy(
                    loading = false,
                    reviewExceptions = uiState.reviewExceptions.filterNot { it.readingGroupId == readingGroupId },
                    lastReading = it,
                )
                refreshProgress(inspection.id)
            }.onFailure { handleAuthenticatedFailure(it) }
        }
    }

    fun backToInspectionFromExceptions() {
        uiState = uiState.copy(screen = AppScreen.INSPECTION, error = null)
    }

    fun startSensorMode(refreshObjective: Boolean = true) {
        val inspection = uiState.inspection ?: return
        locationStability.reset()
        palletStability.reset()
        sensorLocationId = null
        sensorUnresolvedPending = false
        sensorUiState = SensorUiState(
            message = sensorObjective?.locationCode?.let { "Próximo objetivo: $it · ${sensorObjective?.reason ?: "inspección pendiente"}" }
                ?: "Buscando código de ubicación",
        )
        uiState = uiState.copy(screen = AppScreen.SENSOR, inspection = inspection, result = null, error = null)
        if (refreshObjective) refreshSensorObjective()
    }

    /** Fetches a Core directive.  The app can still run older MVP servers that do not provide a target yet. */
    private fun refreshSensorObjective() {
        val device = sensorDevice ?: return
        if (uiState.sensorMission == null) return
        viewModelScope.launch {
            runCatching { AeroTwinApiFactory.createSensor(baseUrl, device.token).sensorNextObjective() }
                .onSuccess { directive ->
                    sensorObjective = directive
                    if (uiState.screen == AppScreen.SENSOR && directive.locationCode != null) {
                        sensorUiState = sensorUiState.copy(
                            message = "Próximo objetivo: ${directive.locationCode} · ${directive.reason}",
                        )
                    }
                }
                .onFailure { Log.w("AeroTwinSensor", "No se pudo recuperar próximo objetivo", it) }
        }
    }

    fun onCameraPermissionChanged(granted: Boolean) {
        if (granted && sensorUiState.phase == SensorPhase.CAMERA_PERMISSION_REQUIRED) {
            sensorUiState = SensorUiState()
        }
        if (!granted) sensorUiState = sensorUiState.copy(
            phase = SensorPhase.CAMERA_PERMISSION_REQUIRED,
            message = "AeroTwin necesita acceso a la cámara para realizar inspecciones.",
        )
    }

    fun onSensorDetections(
        detections: List<CameraBarcodeDetection>,
        imageWidth: Int,
        imageHeight: Int,
        brightness: Float,
    ) {
        if (uiState.loading) return
        val phase = sensorUiState.phase
        // Preserve the confirmed pallet while CameraX finishes the automatic capture.
        if (phase != SensorPhase.SEARCHING_LOCATION && phase != SensorPhase.SEARCHING_PALLET) return
        val expectedLocation = phase == SensorPhase.SEARCHING_LOCATION
        val expectedPallet = phase == SensorPhase.SEARCHING_PALLET

        // --- Grace-period handling when camera sees nothing ---
        if (detections.isEmpty()) {
            if (expectedLocation) locationStability.miss() else palletStability.miss()
            val timedOut = expectedPallet &&
                palletSearchStartedAt > 0 &&
                SystemClock.elapsedRealtime() - palletSearchStartedAt > PALLET_SEARCH_TIMEOUT_MS
            sensorUiState = sensorUiState.copy(
                detections = emptyList(),
                stableFrames = if (expectedLocation) locationStability.currentFrames() else palletStability.currentFrames(),
                message = if (timedOut) "No fue posible confirmar el pallet · capturando observación…" else sensorUiState.message,
            )
            if (timedOut) triggerUnresolvedCapture()
            return
        }

        val parsed = detections.map { it to parseSensorQr(it.rawValue) }

        // --- Select the candidate code that matches the current phase ---
        val targetLocationCode = sensorObjective?.locationCode
        val candidate = parsed.firstOrNull { (_, code) ->
            (expectedLocation && code is SensorQrCode.Location && code.code !in completedSensorLocations &&
                (targetLocationCode == null || code.code == targetLocationCode)) ||
                (expectedPallet && code is SensorQrCode.Pallet)
        }
        var stableFrames = sensorUiState.stableFrames
        var quality: CaptureQuality? = sensorUiState.quality
        val selectedCode = candidate?.second
        selectedCode?.code?.let { reportSensorQrDetected(it) }

        if (selectedCode is SensorQrCode.Location) stableFrames = locationStability.observe(selectedCode.code)
        else if (expectedLocation) locationStability.miss()

        if (selectedCode is SensorQrCode.Pallet) {
            stableFrames = palletStability.observe(selectedCode.code)
            quality = calculateCaptureQuality(stableFrames, candidate!!.first.boundingBox, imageWidth, imageHeight, brightness)
        } else if (expectedPallet) {
            palletStability.miss()
        }

        // --- Build overlays for ALL detections (Rule 12: never hide). ---
        val overlays = parsed.map { (detected, code) ->
            val isRelevant =
                (expectedLocation && code is SensorQrCode.Location &&
                    (targetLocationCode == null || code.code == targetLocationCode)) ||
                    (expectedPallet && code is SensorQrCode.Pallet)
            val selected = code?.code == selectedCode?.code && isRelevant
            val tone = when {
                code == null -> DetectionTone.INVALID
                !isRelevant -> DetectionTone.CANDIDATE  // visible but contextual
                selected && code is SensorQrCode.Pallet && quality != null && quality.score < 40 -> DetectionTone.LOW_QUALITY
                selected && stableFrames >= STABLE_FRAMES_REQUIRED -> DetectionTone.CONFIRMED
                else -> DetectionTone.CANDIDATE
            }
            val contextDetail = when {
                code == null -> "CÓDIGO NO RECONOCIDO"
                !isRelevant && code is SensorQrCode.Pallet -> "Pallet detectado · esperando ubicación"
                !isRelevant && code is SensorQrCode.Location && targetLocationCode != null -> "Ubicación detectada · objetivo Core: $targetLocationCode"
                !isRelevant && code is SensorQrCode.Location -> "Ubicación detectada · buscando pallet"
                tone == DetectionTone.CANDIDATE -> "ANALIZANDO"
                tone == DetectionTone.CONFIRMED -> "VALIDADO"
                tone == DetectionTone.LOW_QUALITY -> "CALIDAD INSUFICIENTE"
                else -> "INCOMPATIBLE"
            }
            SensorDetection(
                rawValue = detected.rawValue,
                format = detected.format,
                code = code?.code,
                kind = when (code) { is SensorQrCode.Location -> "UBICACIÓN"; is SensorQrCode.Pallet -> "PALLET"; null -> null },
                boundingBox = detected.boundingBox,
                frameWidth = imageWidth,
                frameHeight = imageHeight,
                tone = tone,
                detail = contextDetail,
                quality = if (selected && code is SensorQrCode.Pallet) quality?.score else null,
            )
        }

        val timedOut = expectedPallet &&
            selectedCode == null &&
            palletSearchStartedAt > 0 &&
            SystemClock.elapsedRealtime() - palletSearchStartedAt > PALLET_SEARCH_TIMEOUT_MS

        Log.d("AeroTwinSensor", "PALLET_DETECTED phase=$phase STABLE_FRAMES=$stableFrames QUALITY=${quality?.score} detections=${detections.size}")
        sensorUiState = sensorUiState.copy(
            detections = overlays,
            detectedCode = selectedCode?.code,
            stableFrames = stableFrames,
            boundingBox = candidate?.first?.boundingBox,
            frameWidth = imageWidth,
            frameHeight = imageHeight,
            quality = quality,
            message = when {
                selectedCode is SensorQrCode.Location && stableFrames >= STABLE_FRAMES_REQUIRED -> "Validando ubicación…"
                selectedCode is SensorQrCode.Location -> "Código detectado · analizando…"
                selectedCode is SensorQrCode.Pallet && stableFrames >= STABLE_FRAMES_REQUIRED && quality != null && quality.score < MIN_AUTO_CAPTURE_QUALITY -> "Imagen temporal débil · acerca la etiqueta"
                selectedCode is SensorQrCode.Pallet && stableFrames >= STABLE_FRAMES_REQUIRED -> "Validado · capturando evidencia…"
                selectedCode is SensorQrCode.Pallet -> "Código detectado · analizando…"
                parsed.any { it.second?.code in completedSensorLocations } -> "Ubicación ya registrada · enfoca la siguiente"
                timedOut -> "No fue posible confirmar el pallet · capturando observación…"
                else -> if (expectedLocation) "Enfoca primero un QR de ubicación LOC:" else "Enfoca el QR PAL: del pallet"
            },
        )
        if (selectedCode is SensorQrCode.Location && locationStability.isStable(selectedCode.code)) {
            Log.d("AeroTwinSensor", "LOCATION_CONFIRMED code=${selectedCode.code}")
            validateSensorLocation(selectedCode.code)
        }
        if (selectedCode is SensorQrCode.Pallet && palletStability.isStable(selectedCode.code) && (quality?.score ?: 0) >= MIN_AUTO_CAPTURE_QUALITY) {
            Log.d("AeroTwinSensor", "AUTO_CAPTURE_TRIGGERED pallet=${selectedCode.code} quality=${quality?.score}")
            sensorUiState = sensorUiState.copy(phase = SensorPhase.CAPTURING, message = "Capturando evidencia automáticamente…", captureRequest = sensorUiState.captureRequest + 1)
        }
        if (timedOut) triggerUnresolvedCapture()
    }

    private fun validateSensorLocation(code: String) {
        sensorUiState = sensorUiState.copy(phase = SensorPhase.VALIDATING_LOCATION)
        viewModelScope.launch {
            runCatching {
                val device = sensorDevice
                if (device != null && uiState.sensorMission != null) {
                    AeroTwinApiFactory.createSensor(baseUrl, device.token).sensorLocation(code).let { it.id to it.code }
                } else {
                    AeroTwinApiFactory.create(baseUrl, token).location(code).let { it.id to it.code }
                }
            }
                .onSuccess { location ->
                    sensorLocationId = location.first
                    locationCode = location.second
                    palletStability.reset()
                    palletSearchStartedAt = SystemClock.elapsedRealtime()
                    sensorUiState = sensorUiState.copy(
                        phase = SensorPhase.SEARCHING_PALLET,
                        locationCode = location.second,
                        detectedCode = null,
                        stableFrames = 0,
                        boundingBox = null,
                        message = "Ubicación válida · buscando pallet",
                    )
                }
                .onFailure {
                    locationStability.reset()
                    sensorUiState = sensorUiState.copy(
                        phase = SensorPhase.SEARCHING_LOCATION,
                        message = apiMessage(it),
                    )
                }
        }
    }

    private fun triggerUnresolvedCapture() {
        if (sensorUiState.phase != SensorPhase.SEARCHING_PALLET) return
        sensorUnresolvedPending = true
        Log.d("AeroTwinSensor", "AUTO_CAPTURE_TRIGGERED unresolved attempt=$attemptNumber")
        sensorUiState = sensorUiState.copy(
            phase = SensorPhase.CAPTURING,
            message = "Capturando observación no resuelta…",
            captureRequest = sensorUiState.captureRequest + 1,
        )
    }

    fun onSensorImageCaptured(file: File) {
        val inspection = uiState.inspection ?: return
        val locationId = sensorLocationId ?: return
        val detectedPallet = sensorUiState.detectedCode
        Log.d("AeroTwinSensor", "IMAGE_CAPTURED unresolved=$sensorUnresolvedPending pallet=$detectedPallet")
        viewModelScope.launch {
            sensorUiState = sensorUiState.copy(phase = SensorPhase.PROCESSING, message = "Procesando lectura en AeroTwin Core…")
            runCatching { withContext(Dispatchers.IO) { prepareEvidence(file) } }
                .onSuccess { prepared ->
                    submitPreparedReading(
                        inspection = inspection,
                        locationId = locationId,
                        preparedEvidence = prepared,
                        sourceType = "ANDROID_CAMERA",
                        observedPallet = if (sensorUnresolvedPending) null else detectedPallet,
                        observed = if (sensorUnresolvedPending) "UNRESOLVED" else "PALLET",
                        quality = if (sensorUnresolvedPending) 0 else (sensorUiState.quality?.score ?: 0),
                        emptyConfirmed = false,
                        sensorMode = true,
                    )
                }
                .onFailure {
                    sensorUiState = sensorUiState.copy(phase = SensorPhase.SEARCHING_PALLET, message = "No pudimos preparar la captura. Reintentando…")
                }
        }
    }

    fun onSensorCaptureFailed() {
        if (sensorUiState.phase == SensorPhase.CAPTURING || sensorUiState.phase == SensorPhase.PROCESSING) {
            sensorUiState = sensorUiState.copy(
                phase = if (sensorLocationId == null) SensorPhase.SEARCHING_LOCATION else SensorPhase.SEARCHING_PALLET,
                message = "No se pudo capturar. Continúa enfocando el código.",
            )
        }
    }

    private fun prepareReading(inspection: InspectionDto) {
        if (locationCode.isBlank()) locationCode = "${inspection.zoneCode}-01-01"
        uiState = uiState.copy(
            screen = AppScreen.READING,
            loading = false,
            inspection = inspection,
            result = null,
            error = null,
        )
    }

    fun submitReading() {
        val inspection = uiState.inspection ?: return
        val quality = qualityScore.toIntOrNull()
        if (locationCode.isBlank() || quality == null || quality !in 0..100) {
            uiState = uiState.copy(error = "Ingresa una ubicación y una calidad entre 0 y 100.")
            return
        }
        if (observedState == "PALLET" && palletCode.isBlank()) {
            uiState = uiState.copy(error = "Ingresa el pallet observado.")
            return
        }
        val preparedEvidence = evidence
        if (preparedEvidence == null) {
            uiState = uiState.copy(error = "Selecciona una imagen de evidencia antes de enviar.")
            return
        }
        viewModelScope.launch {
            val location = runCatching { AeroTwinApiFactory.create(baseUrl, token).location(locationCode.trim()) }
                .getOrElse { handleAuthenticatedFailure(it); return@launch }
            submitPreparedReading(inspection, location.id, preparedEvidence, "MANUAL_DEMO", palletCode.trim().ifBlank { null }, observedState, quality, observedState == "EMPTY", false)
        }
    }

    private fun submitPreparedReading(
        inspection: InspectionDto,
        locationId: Int,
        preparedEvidence: PreparedEvidence,
        sourceType: String,
        observedPallet: String?,
        observed: String,
        quality: Int,
        emptyConfirmed: Boolean,
        sensorMode: Boolean,
    ) {
        viewModelScope.launch {
            uiState = uiState.copy(loading = true, error = null)
            runCatching {
                Log.d("AeroTwinSensor", "UPLOAD_STARTED attempt=$attemptNumber observed=$observed quality=$quality")
                val request = ReadingCreateRequest(clientReadingId, locationId, readingGroupId, attemptNumber, observedPallet, observed, quality, sourceType, emptyConfirmed)
                val payload = AeroTwinApiFactory.gson.toJson(request).toRequestBody("application/json".toMediaType())
                val image = MultipartBody.Part.createFormData("evidence", "sensor-evidence.jpg", preparedEvidence.jpegBytes.toRequestBody("image/jpeg".toMediaType()))
                if (sensorMode) {
                    val device = sensorDevice ?: throw IOException("El sensor no está vinculado.")
                    AeroTwinApiFactory.createSensor(baseUrl, device.token).submitSensorReading(payload, image)
                } else {
                    AeroTwinApiFactory.create(baseUrl, token).submitReading(inspection.id, payload, image)
                }
            }.onSuccess { result ->
                Log.d("AeroTwinSensor", "READING_RESPONSE status=${result.readingStatus} result=${result.comparisonResult}")
                uiState = uiState.copy(loading = false, result = result, lastReading = result)
                if (result.readingStatus == "RESCAN_REQUIRED") {
                    attemptNumber += 1
                    clientReadingId = UUID.randomUUID().toString()
                    evidence = null
                    if (sensorMode) {
                        sensorUnresolvedPending = false
                        palletStability.reset()
                        palletSearchStartedAt = SystemClock.elapsedRealtime()
                        sensorUiState = sensorUiState.copy(
                            phase = SensorPhase.SEARCHING_PALLET,
                            previousQuality = result.qualityScore,
                            detectedCode = null,
                            stableFrames = 0,
                            boundingBox = null,
                            quality = null,
                            message = "No fue posible confirmar el pallet · reintentando observación $attemptNumber / 2…",
                        )
                    }
                } else {
                    if (sensorMode) {
                        sensorUiState = sensorUiState.copy(
                            phase = SensorPhase.RESULT,
                            message = if (result.readingStatus == "HUMAN_REVIEW_REQUIRED") "Lectura no resuelta · caso enviado a supervisión" else "Lectura completada · enviada al Core",
                        )
                        if (result.isFinal) {
                            sensorUiState.locationCode?.let(completedSensorLocations::add)
                            refreshSensorProgress()
                            advanceSensorObjectiveAfterResult()
                        }
                    }
                    if (result.isFinal && !sensorMode) refreshProgress(inspection.id)
                }
            }.onFailure {
                if (sensorMode) sensorUiState = sensorUiState.copy(phase = SensorPhase.SEARCHING_PALLET, message = "No pudimos sincronizar. El sensor conserva el intento para reintentar.")
                if (sensorMode) uiState = uiState.copy(loading = false, error = apiMessage(it)) else handleAuthenticatedFailure(it)
            }
        }
    }

    fun refreshProgress(inspectionId: Int) {
        viewModelScope.launch {
            runCatching {
                AeroTwinApiFactory.create(baseUrl, token).inspection(inspectionId)
            }.onSuccess { uiState = uiState.copy(inspection = it) }
        }
    }

    private fun refreshSensorProgress() {
        val device = sensorDevice ?: return
        viewModelScope.launch {
            runCatching { AeroTwinApiFactory.createSensor(baseUrl, device.token).sensorMissionProgress() }
                .onSuccess { uiState = uiState.copy(inspection = it) }
        }
    }

    fun nextReading() {
        readingGroupId = UUID.randomUUID().toString()
        attemptNumber = 1
        clientReadingId = UUID.randomUUID().toString()
        locationCode = ""
        palletCode = ""
        qualityScore = "95"
        observedState = "PALLET"
        evidence = null
        uiState = uiState.copy(result = null, error = null)
    }

    fun backToHome() {
        readingGroupId = UUID.randomUUID().toString()
        attemptNumber = 1
        clientReadingId = UUID.randomUUID().toString()
        evidence = null
        uiState = uiState.copy(screen = AppScreen.HOME, result = null, error = null)
        loadHome()
    }

    fun backToInspection() {
        readingGroupId = UUID.randomUUID().toString()
        attemptNumber = 1
        clientReadingId = UUID.randomUUID().toString()
        evidence = null
        uiState = uiState.copy(screen = AppScreen.INSPECTION, result = null, error = null)
    }

    /** The Core directive, rather than Sensor UI, owns the next target decision. */
    private fun advanceSensorObjectiveAfterResult() {
        viewModelScope.launch {
            delay(1_500)
            val device = sensorDevice ?: return@launch
            val directive = runCatching { AeroTwinApiFactory.createSensor(baseUrl, device.token).sensorNextObjective() }.getOrNull()
            sensorObjective = directive
            // ``COMPLETE_MISSION`` is the Core terminal directive used by the
            // live-state/mission-next contract.  Keep the older
            // ``MISSION_COMPLETE`` spelling here too so a sensor never loops
            // back into camera mode after its final persisted reading.
            val shouldContinue = directive?.action?.uppercase() !in setOf(
                null,
                "COMPLETE_MISSION",
                "MISSION_COMPLETE",
                "WAIT",
                "STOP",
            )
            if (shouldContinue) {
                nextReading()
                startSensorMode(refreshObjective = false)
            } else {
                returnToSensorWaiting()
            }
        }
    }

    fun returnToSensorWaiting() {
        sensorUiState = SensorUiState(message = "Esperando misión…")
        sensorObjective = null
        uiState = uiState.copy(screen = AppScreen.SENSOR_WAITING, result = null, sensorMission = null, error = null)
        startSensorMissionPolling()
    }

    fun logout() {
        sessionStore.clear()
        token = ""
        uiState = AppUiState(screen = AppScreen.MODE_SELECTION, coreConnected = baseUrl.isNotBlank())
    }

    fun editConnection() {
        showServerConfiguration = true
        uiState = AppUiState(screen = AppScreen.CONNECTION)
    }

    private fun handleAuthenticatedFailure(error: Throwable) {
        if (error is HttpException && error.code() == 401) {
            sessionStore.clear()
            token = ""
            uiState = AppUiState(screen = AppScreen.LOGIN, error = "La sesión expiró.")
        } else {
            uiState = uiState.copy(loading = false, error = apiMessage(error))
        }
    }

    private fun apiMessage(error: Throwable): String {
        if (error is HttpException) {
            val parsed = runCatching {
                AeroTwinApiFactory.gson.fromJson(
                    error.response()?.errorBody()?.string(),
                    ErrorBody::class.java,
                )
            }.getOrNull()
            return parsed?.error?.message ?: "El servidor rechazó la solicitud (${error.code()})."
        }
        return when (error) {
            is IOException -> "No se pudo comunicar con AeroTwin Core."
            else -> "No pudimos completar la acción. Intenta nuevamente."
        }
    }

    private fun prepareEvidence(uri: Uri): PreparedEvidence {
        val resolver = getApplication<Application>().contentResolver
        val decoded = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            ImageDecoder.decodeBitmap(ImageDecoder.createSource(resolver, uri)) { decoder, info, _ ->
                decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
                val longest = maxOf(info.size.width, info.size.height)
                if (longest > 2560) {
                    val scale = 2560f / longest
                    decoder.setTargetSize((info.size.width * scale).toInt(), (info.size.height * scale).toInt())
                }
            }
        } else {
            resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it) }
        } ?: throw IOException("No se pudo decodificar la imagen.")
        if (decoded.width <= 0 || decoded.height <= 0) throw IOException("Imagen inválida.")
        val scaled = if (maxOf(decoded.width, decoded.height) > 1280) {
            val scale = 1280f / maxOf(decoded.width, decoded.height)
            Bitmap.createScaledBitmap(decoded, (decoded.width * scale).toInt(), (decoded.height * scale).toInt(), true)
        } else decoded
        if (scaled !== decoded) decoded.recycle()
        val output = ByteArrayOutputStream()
        scaled.compress(Bitmap.CompressFormat.JPEG, 80, output)
        return PreparedEvidence(scaled, output.toByteArray())
    }

    private fun prepareEvidence(file: File): PreparedEvidence = prepareEvidence(Uri.fromFile(file))
}
