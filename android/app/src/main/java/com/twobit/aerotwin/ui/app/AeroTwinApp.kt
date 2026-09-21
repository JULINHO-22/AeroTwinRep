package com.twobit.aerotwin.ui.app

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowForward
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.automirrored.outlined.FactCheck
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Warehouse
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material.icons.outlined.Wifi
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import kotlinx.coroutines.delay
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.twobit.aerotwin.core.sensor.SensorPhase
import com.twobit.aerotwin.core.sensor.SensorUiState
import com.twobit.aerotwin.data.api.InspectionDto
import com.twobit.aerotwin.data.api.LiveInspectionStateDto
import com.twobit.aerotwin.data.api.LiveLocationDto
import com.twobit.aerotwin.data.api.ReadingDto
import com.twobit.aerotwin.data.api.ZoneDto
import com.twobit.aerotwin.ui.design.ActionButton
import com.twobit.aerotwin.ui.design.AeroDivider
import com.twobit.aerotwin.ui.design.AeroStatusTone
import com.twobit.aerotwin.ui.design.AeroTopBar
import com.twobit.aerotwin.ui.design.ConnectionIndicator
import com.twobit.aerotwin.ui.design.InspectionProgress
import com.twobit.aerotwin.ui.design.MetricTile
import com.twobit.aerotwin.ui.design.OperationalCode
import com.twobit.aerotwin.ui.design.SectionHeader
import com.twobit.aerotwin.ui.design.SecondaryAction
import com.twobit.aerotwin.ui.design.StateBanner
import com.twobit.aerotwin.ui.design.StatusBadge
import com.twobit.aerotwin.ui.theme.AeroTwinColors
import com.twobit.aerotwin.ui.sensor.SensorBoundingBox
import com.twobit.aerotwin.ui.sensor.SensorCameraPreview

@Composable
fun AeroTwinApp(viewModel: AeroTwinViewModel) {
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> viewModel.setAppInForeground(true)
                Lifecycle.Event.ON_PAUSE -> viewModel.setAppInForeground(false)
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        viewModel.setAppInForeground(lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED))
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            viewModel.setAppInForeground(false)
        }
    }
    when (viewModel.uiState.screen) {
        AppScreen.CONNECTION -> ConnectionPage(viewModel)
        AppScreen.MODE_SELECTION -> ModeSelectionPage(viewModel)
        AppScreen.LOGIN -> LoginPage(viewModel)
        AppScreen.HOME -> SupervisorShell(AppScreen.HOME, viewModel) { HomePage(viewModel) }
        AppScreen.TWIN -> SupervisorShell(AppScreen.TWIN, viewModel) { TwinPage(viewModel) }
        AppScreen.ZONE_SELECTION -> ZoneSelectionPage(viewModel)
        AppScreen.INSPECTION -> InspectionPage(viewModel)
        AppScreen.READING -> ReadingPage(viewModel)
        AppScreen.SENSOR_PAIRING -> SensorPairingPage(viewModel)
        AppScreen.SENSOR_WAITING -> SensorWaitingPage(viewModel)
        AppScreen.SENSOR -> SensorPage(viewModel)
        AppScreen.DRONE_MONITOR -> DroneMonitorPage(viewModel)
        AppScreen.SUPERVISOR_EXCEPTIONS -> SupervisorExceptionsPage(viewModel)
        AppScreen.EXCEPTIONS -> SupervisorShell(AppScreen.EXCEPTIONS, viewModel) { ExceptionsPage(viewModel) }
        AppScreen.EXCEPTION_DETAIL -> ExceptionDetailPage(viewModel)
        AppScreen.FLOWTWIN_CHANGES -> FlowTwinChangesPage(viewModel)
        AppScreen.AGENT -> SupervisorShell(AppScreen.AGENT, viewModel) { AgentPage(viewModel) }
        AppScreen.LOCATION_HISTORY -> LocationHistoryPage(viewModel)
        AppScreen.EVIDENCE -> EvidencePage(viewModel)
    }
}

/** Four destinations are enough for the supervisor; monitoring remains an operational action, not a fifth dashboard. */
@Composable
private fun SupervisorShell(selected: AppScreen, viewModel: AeroTwinViewModel, content: @Composable () -> Unit) {
    Scaffold(
        containerColor = AeroTwinColors.Background,
        bottomBar = {
            NavigationBar(containerColor = AeroTwinColors.Surface) {
                NavigationBarItem(
                    selected = selected == AppScreen.HOME,
                    onClick = viewModel::loadHome,
                    icon = { Icon(Icons.Outlined.Home, contentDescription = null) },
                    label = { Text("Inicio") },
                )
                NavigationBarItem(
                    selected = selected == AppScreen.TWIN,
                    onClick = viewModel::openTwin,
                    icon = { Icon(Icons.Outlined.Warehouse, contentDescription = null) },
                    label = { Text("Gemelo") },
                )
                NavigationBarItem(
                    selected = selected == AppScreen.EXCEPTIONS,
                    onClick = viewModel::openExceptions,
                    icon = { Icon(Icons.Outlined.WarningAmber, contentDescription = null) },
                    label = { Text("Excepciones") },
                )
                NavigationBarItem(
                    selected = selected == AppScreen.AGENT,
                    onClick = viewModel::openAgent,
                    icon = { Icon(Icons.AutoMirrored.Outlined.FactCheck, contentDescription = null) },
                    label = { Text("Agente") },
                )
            }
        },
    ) { innerPadding ->
        Box(Modifier.fillMaxSize().padding(innerPadding)) { content() }
    }
}

@Composable
private fun ModeSelectionPage(viewModel: AeroTwinViewModel) {
    Screen {
        Spacer(Modifier.height(42.dp))
        AeroTopBar("AEROTWIN", "¿Cómo se utilizará este dispositivo?", "Selecciona el rol de esta estación antes de continuar.")
        Spacer(Modifier.height(34.dp))
        ActionButton("MODO OPERADOR", viewModel::chooseOperatorMode, icon = Icons.AutoMirrored.Outlined.FactCheck)
        Spacer(Modifier.height(14.dp))
        SecondaryAction("MODO SENSOR", viewModel::chooseSensorMode)
        Spacer(Modifier.height(20.dp))
        ConnectionIndicator(connected = viewModel.uiState.coreConnected)
        Spacer(Modifier.height(10.dp))
        TextButton(onClick = viewModel::editConnection) { Text("Configuración técnica", color = AeroTwinColors.TextSecondary) }
    }
}

@Composable
private fun SensorPairingPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    Screen {
        Spacer(Modifier.height(12.dp))
        AeroTopBar("AeroTwin Sensor", "Vincular dispositivo", "Este teléfono se autentica como sensor; no necesita credenciales humanas.", showBack = true, onBack = viewModel::backToModeSelection)
        Spacer(Modifier.height(28.dp))
        SectionHeader("Servidor")
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(value = viewModel.baseUrl, onValueChange = viewModel::onBaseUrlChanged, modifier = Modifier.fillMaxWidth(), label = { Text("Servidor") }, singleLine = true, shape = RoundedCornerShape(8.dp))
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(value = viewModel.sensorName, onValueChange = viewModel::onSensorNameChanged, modifier = Modifier.fillMaxWidth(), label = { Text("Nombre") }, singleLine = true, shape = RoundedCornerShape(8.dp))
        Spacer(Modifier.height(24.dp))
        ActionButton(if (state.loading) "VINCULANDO…" else "VINCULAR DISPOSITIVO", viewModel::pairSensor, enabled = !state.loading, icon = Icons.Outlined.Wifi)
        ErrorMessage(state.error)
    }
}

@Composable
private fun SensorWaitingPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    Screen {
        Spacer(Modifier.height(12.dp))
        AeroTopBar("AeroTwin Sensor", viewModel.sensorName.uppercase(), "Este dispositivo está vinculado y no almacena credenciales de operador.", showBack = true, onBack = viewModel::backToModeSelection)
        Spacer(Modifier.height(30.dp))
        ConnectionIndicator(connected = state.coreConnected, label = "● Conectado")
        Spacer(Modifier.height(28.dp))
        StateBanner("Esperando misión…", "El Control Station debe asignar una inspección activa a este sensor.", AeroStatusTone.INFO, Icons.Outlined.Wifi)
        Spacer(Modifier.height(24.dp))
        ActionButton(if (state.loading) "CONSULTANDO MISIÓN…" else "ACTUALIZAR MISIÓN", viewModel::refreshSensorMission, enabled = !state.loading, icon = Icons.Outlined.Refresh)
        ErrorMessage(state.error)
    }
}

@Composable
private fun Screen(content: @Composable () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(AeroTwinColors.Background)
            .verticalScroll(rememberScrollState())
            .padding(start = 20.dp, end = 20.dp, top = 46.dp, bottom = 24.dp),
        content = { content() },
    )
}

@Composable
private fun ConnectionPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    Screen {
        if (state.loading && !viewModel.showServerConfiguration) {
            Spacer(Modifier.height(112.dp))
            Icon(Icons.Outlined.Wifi, null, tint = AeroTwinColors.Primary, modifier = Modifier.height(34.dp))
            Spacer(Modifier.height(24.dp))
            AeroTopBar("Inicializando operación", "Conectando con Core", "Comprobando el acceso a AeroTwin Core.")
            Spacer(Modifier.height(24.dp))
            CircularProgressIndicator(color = AeroTwinColors.Primary, strokeWidth = 2.dp)
        } else if (state.error != null && !viewModel.showServerConfiguration) {
            AeroTopBar("Conectividad", "Core no disponible", "No fue posible recuperar la conexión de esta estación.")
            Spacer(Modifier.height(32.dp))
            StateBanner("Conexión requerida", state.error, AeroStatusTone.CRITICAL, Icons.Outlined.ErrorOutline)
            Spacer(Modifier.height(24.dp))
            ActionButton("CONFIGURAR SERVIDOR", viewModel::showServerConfiguration, icon = Icons.Outlined.Settings)
        } else {
            AeroTopBar("Configuración técnica", "AeroTwin Core", "Define la dirección del servidor de esta estación de operación.")
            Spacer(Modifier.height(30.dp))
            SectionHeader("Servidor")
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(
                value = viewModel.baseUrl,
                onValueChange = viewModel::onBaseUrlChanged,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Dirección del backend") },
                placeholder = { Text("http://192.168.X.X:8000") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                singleLine = true,
                shape = RoundedCornerShape(8.dp),
            )
            Spacer(Modifier.height(12.dp))
            Text("Solo para la red privada de desarrollo.", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
            Spacer(Modifier.height(24.dp))
            ActionButton(
                text = if (state.loading) "CONECTANDO…" else "CONECTAR CON CORE",
                enabled = !state.loading,
                onClick = viewModel::testConnection,
                icon = Icons.Outlined.Wifi,
            )
            ErrorMessage(state.error)
        }
    }
}

@Composable
private fun LoginPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    var passwordVisible by remember { mutableStateOf(false) }
    Screen {
        Spacer(Modifier.height(36.dp))
        AeroTopBar("Physical Inventory Intelligence", "Acceso de operador", "Ingresa para iniciar una verificación física de inventario.")
        Spacer(Modifier.height(30.dp))
        ConnectionIndicator(connected = state.coreConnected)
        Spacer(Modifier.height(24.dp))
        AeroDivider()
        Spacer(Modifier.height(24.dp))
        SectionHeader("Credenciales")
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = viewModel.username,
            onValueChange = viewModel::onUsernameChanged,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Usuario") },
            singleLine = true,
            shape = RoundedCornerShape(8.dp),
        )
        Spacer(Modifier.height(14.dp))
        OutlinedTextField(
            value = viewModel.password,
            onValueChange = viewModel::onPasswordChanged,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Contraseña") },
            visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            singleLine = true,
            shape = RoundedCornerShape(8.dp),
            trailingIcon = {
                IconButton(onClick = { passwordVisible = !passwordVisible }) {
                    Icon(
                        imageVector = if (passwordVisible) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                        contentDescription = if (passwordVisible) "Ocultar contraseña" else "Mostrar contraseña",
                    )
                }
            },
        )
        Spacer(Modifier.height(24.dp))
        ActionButton(
            text = if (state.loading) "VALIDANDO…" else "ACCEDER",
            enabled = !state.loading,
            onClick = viewModel::login,
            icon = Icons.AutoMirrored.Outlined.ArrowForward,
        )
        ErrorMessage(state.error)
        Spacer(Modifier.height(12.dp))
        TextButton(onClick = viewModel::editConnection) { Text("Configuración técnica", color = AeroTwinColors.TextSecondary) }
    }
}

@Composable
private fun HomePage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    Screen {
        AeroTopBar("Centro de operaciones", "Estado del inventario", "Prioridades calculadas por AeroTwin Core.")
        Spacer(Modifier.height(18.dp))
        ConnectionIndicator(connected = state.coreConnected)
        Spacer(Modifier.height(24.dp))
        AeroDivider()
        Spacer(Modifier.height(24.dp))
        if (state.loading) LoadingState("Actualizando inteligencia de inventario") else state.dashboard?.let { DashboardSummary(it, viewModel) } ?: NoInspectionSummary(viewModel::openZoneSelection)
        ErrorMessage(state.error)
        Spacer(Modifier.height(18.dp))
        TextButton(onClick = viewModel::logout) { Text("Cerrar sesión", color = AeroTwinColors.TextSecondary) }
    }
}

@Composable
private fun DashboardSummary(dashboard: com.twobit.aerotwin.data.api.DashboardDto, viewModel: AeroTwinViewModel) {
    val live = viewModel.uiState.liveState
    val inspectionActive = live != null || dashboard.inspection.active

    SectionHeader(if (inspectionActive) "Inspección activa" else "Inspección")
    Spacer(Modifier.height(12.dp))
    if (inspectionActive) {
        val total = live?.total ?: dashboard.inspection.total
        val inspected = live?.inspected ?: dashboard.inspection.verified
        val validated = live?.validated ?: dashboard.inspection.verified
        val reviewRequired = live?.reviewRequired ?: dashboard.exceptions.humanReview
        val pending = live?.pending ?: (total - inspected).coerceAtLeast(0)
        OperationalCode("Zona", live?.zone ?: dashboard.inspection.zoneCode ?: "—", AeroTwinColors.PrimaryDark)
        Spacer(Modifier.height(14.dp))
        InspectionProgress(inspected, total)
        Spacer(Modifier.height(10.dp))
        Text(
            "$validated validadas · $reviewRequired en revisión · $pending pendientes",
            color = AeroTwinColors.TextSecondary,
            fontSize = 13.sp,
        )
        live?.currentTarget?.let { target ->
            Spacer(Modifier.height(14.dp))
            StateBanner(
                "Próximo objetivo",
                target.locationCode?.let { code -> "$code · ${target.reason ?: "prioridad de inspección"}" }
                    ?: target.reason ?: "Core está determinando el siguiente objetivo.",
                AeroStatusTone.INFO,
            )
        }
        Spacer(Modifier.height(14.dp))
        SecondaryAction("ABRIR GEMELO EN VIVO", viewModel::openTwin)
    } else {
        StateBanner(
            "Sin inspección activa",
            "Selecciona una zona para comenzar a construir el gemelo físico.",
            AeroStatusTone.NEUTRAL,
            Icons.Outlined.Warehouse,
        )
        Spacer(Modifier.height(14.dp))
        SecondaryAction("SELECCIONAR ZONA", viewModel::openZoneSelection)
    }

    Spacer(Modifier.height(24.dp))
    SectionHeader("Prioridad ahora")
    Spacer(Modifier.height(10.dp))
    if (dashboard.priorities.isEmpty()) {
        StateBanner("Sin excepciones abiertas", "La operación no tiene prioridades pendientes.", AeroStatusTone.SUCCESS, Icons.Outlined.CheckCircle)
    } else {
        dashboard.priorities.take(3).forEach { item ->
            OutlinedButton(onClick = { viewModel.openExceptionDetail(item.id) }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(8.dp)) {
                Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.Start) {
                    Text(item.location, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, color = AeroTwinColors.TextPrimary)
                    Text(item.shortReason, color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
                    Text("Riesgo ${item.riskScore} · ${agentSeverityLabel(item.severity)}", color = AeroTwinColors.Primary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                }
            }
            Spacer(Modifier.height(8.dp))
        }
        SecondaryAction("VER EXCEPCIONES", viewModel::openExceptions)
    }

    val risks = dashboard.inventoryRisks
    if (risks.expiringSoon > 0 || risks.lowCoverage > 0 || risks.fefo > 0) {
        Spacer(Modifier.height(24.dp))
        SectionHeader("Riesgos a vigilar")
        Spacer(Modifier.height(10.dp))
        val riskSummary = buildList {
            if (risks.expiringSoon > 0) add("${risks.expiringSoon} próximos a vencer")
            if (risks.lowCoverage > 0) add("${risks.lowCoverage} con cobertura baja")
            if (risks.fefo > 0) add("${risks.fefo} con riesgo FEFO")
        }.take(2).joinToString(" · ")
        StateBanner("Inventario requiere atención", riskSummary, AeroStatusTone.WARNING, Icons.Outlined.WarningAmber)
    }

    Spacer(Modifier.height(24.dp))
    SectionHeader("Sensor activo")
    Spacer(Modifier.height(10.dp))
    val activeSensor = dashboard.sensors.firstOrNull()
    StateBanner(
        activeSensor?.name ?: "Sin sensor en línea",
        activeSensor?.let { "● ${it.code} · ${it.status}" } ?: "Conecta un Sensor para transmitir la inspección en vivo.",
        if (activeSensor != null) AeroStatusTone.INFO else AeroStatusTone.NEUTRAL,
        Icons.Outlined.Wifi,
    )
    if (inspectionActive) {
        Spacer(Modifier.height(12.dp))
        SecondaryAction("MONITOREAR INSPECCIÓN", viewModel::monitorDrone, enabled = viewModel.uiState.inspection != null)
    }
}

/** The physical and WMS views are intentionally not another analytics dashboard. */
private enum class TwinDisplayMode { STATUS, EXPECTED_OBSERVED }

@Composable
private fun TwinPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    val live = state.liveState
    var displayMode by remember(live?.inspectionId) { mutableStateOf(TwinDisplayMode.STATUS) }
    var selectedLocationCode by remember(live?.inspectionId) { mutableStateOf<String?>(null) }
    val locations = live?.locations.orEmpty()
    val selected = locations.firstOrNull { it.code == selectedLocationCode } ?: locations.firstOrNull()

    Screen {
        AeroTopBar(
            "Gemelo digital vivo",
            live?.zone?.let { "Zona $it" } ?: "Gemelo",
            "La representación se actualiza cuando Core persiste una lectura final.",
            showBack = true,
            onBack = viewModel::loadHome,
        )
        Spacer(Modifier.height(18.dp))
        if (live == null) {
            if (state.loading) LoadingState("Cargando estado físico de la inspección")
            StateBanner(
                "Sin proyección activa",
                "No hay una inspección activa de la que construir el gemelo.",
                AeroStatusTone.NEUTRAL,
                Icons.Outlined.Warehouse,
            )
            Spacer(Modifier.height(14.dp))
            SecondaryAction("VOLVER A INICIO", viewModel::loadHome)
        } else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                OperationalCode("Cobertura", "${live.coveragePercent.formatPercent()}%", AeroTwinColors.PrimaryDark)
                StatusBadge("En vivo", AeroStatusTone.INFO)
            }
            Spacer(Modifier.height(6.dp))
            Text("Datos WMS demo: SKUs, pallets, lotes y cantidades son sintéticos.", color = AeroTwinColors.TextSecondary, fontSize = 11.sp)
            Spacer(Modifier.height(14.dp))
            InspectionProgress(live.inspected, live.total)
            Spacer(Modifier.height(8.dp))
            Text(
                "${live.validated} correctas · ${live.reviewRequired} en revisión · ${live.pending} pendientes",
                color = AeroTwinColors.TextSecondary,
                fontSize = 13.sp,
            )
            live.currentTarget?.let { target ->
                Spacer(Modifier.height(16.dp))
                StateBanner(
                    "Próximo objetivo",
                    target.locationCode?.let { "$it · ${target.reason ?: "prioridad de Core"}" }
                        ?: target.reason ?: "Core está determinando el siguiente objetivo.",
                    AeroStatusTone.INFO,
                )
            }
            live.lastFinalReading?.let { reading ->
                Spacer(Modifier.height(12.dp))
                Text(
                    "Última lectura final: ${reading.locationCode ?: "—"} · ${operationalLabel(reading.comparisonResult)}",
                    color = AeroTwinColors.TextSecondary,
                    fontSize = 12.sp,
                )
            }
            Spacer(Modifier.height(22.dp))
            TwinModeSwitcher(displayMode) { displayMode = it }
            Spacer(Modifier.height(16.dp))
            when (displayMode) {
                TwinDisplayMode.STATUS -> {
                    SectionHeader("Estado físico")
                    Spacer(Modifier.height(8.dp))
                    TwinStateLegend()
                    Spacer(Modifier.height(12.dp))
                    TwinRack(
                        locations = locations,
                        selectedCode = selected?.code,
                        targetCode = live.currentTarget?.locationCode,
                        presentation = TwinRackPresentation.PHYSICAL,
                        onSelect = { selectedLocationCode = it.code },
                    )
                }
                TwinDisplayMode.EXPECTED_OBSERVED -> {
                    SectionHeader("WMS esperado")
                    Spacer(Modifier.height(10.dp))
                    TwinRack(
                        locations = locations,
                        selectedCode = selected?.code,
                        targetCode = live.currentTarget?.locationCode,
                        presentation = TwinRackPresentation.EXPECTED,
                        onSelect = { selectedLocationCode = it.code },
                    )
                    Spacer(Modifier.height(22.dp))
                    SectionHeader("Última inspección")
                    Spacer(Modifier.height(10.dp))
                    TwinRack(
                        locations = locations,
                        selectedCode = selected?.code,
                        targetCode = live.currentTarget?.locationCode,
                        presentation = TwinRackPresentation.OBSERVED,
                        onSelect = { selectedLocationCode = it.code },
                    )
                }
            }
            selected?.let { location ->
                Spacer(Modifier.height(24.dp))
                TwinPositionDetail(location, viewModel)
            }
            Spacer(Modifier.height(18.dp))
            SecondaryAction("MONITOREAR INSPECCIÓN EN VIVO", viewModel::monitorDrone)
        }
        ErrorMessage(state.error)
    }
}

@Composable
private fun TwinModeSwitcher(selected: TwinDisplayMode, onSelected: (TwinDisplayMode) -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        OutlinedButton(
            onClick = { onSelected(TwinDisplayMode.STATUS) },
            modifier = Modifier.weight(1f),
            shape = RoundedCornerShape(8.dp),
        ) {
            Text("ESTADO", color = if (selected == TwinDisplayMode.STATUS) AeroTwinColors.Primary else AeroTwinColors.TextSecondary, fontWeight = FontWeight.Bold, fontSize = 12.sp)
        }
        OutlinedButton(
            onClick = { onSelected(TwinDisplayMode.EXPECTED_OBSERVED) },
            modifier = Modifier.weight(1f),
            shape = RoundedCornerShape(8.dp),
        ) {
            Text("ESPERADO / OBSERVADO", color = if (selected == TwinDisplayMode.EXPECTED_OBSERVED) AeroTwinColors.Primary else AeroTwinColors.TextSecondary, fontWeight = FontWeight.Bold, fontSize = 11.sp)
        }
    }
}

private enum class TwinRackPresentation { PHYSICAL, EXPECTED, OBSERVED }

@Composable
private fun TwinRack(
    locations: List<LiveLocationDto>,
    selectedCode: String?,
    targetCode: String?,
    presentation: TwinRackPresentation,
    onSelect: (LiveLocationDto) -> Unit,
) {
    if (locations.isEmpty()) {
        StateBanner("Sin posiciones", "Core aún no devolvió posiciones para esta inspección.", AeroStatusTone.NEUTRAL)
        return
    }
    twinRows(locations).forEach { row ->
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            row.forEach { location ->
                TwinPositionCell(
                    location = location,
                    isSelected = location.code == selectedCode,
                    isTarget = location.code == targetCode,
                    presentation = presentation,
                    onClick = { onSelect(location) },
                    modifier = Modifier.weight(1f),
                )
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun TwinPositionCell(
    location: LiveLocationDto,
    isSelected: Boolean,
    isTarget: Boolean,
    presentation: TwinRackPresentation,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val physicalState = location.physicalState ?: location.result ?: "UNINSPECTED"
    val background by animateColorAsState(
        targetValue = when (presentation) {
            TwinRackPresentation.EXPECTED -> if (location.expectedPalletCode == null) AeroTwinColors.SurfaceSubtle else AeroTwinColors.InfoSoft
            TwinRackPresentation.OBSERVED, TwinRackPresentation.PHYSICAL -> twinStateBackground(physicalState)
        },
        label = "twin-cell-${location.code}",
    )
    val borderColor = when {
        isSelected -> AeroTwinColors.Primary
        isTarget -> AeroTwinColors.Info
        else -> twinStateColor(physicalState)
    }
    val primary = when (presentation) {
        TwinRackPresentation.PHYSICAL -> twinPhysicalLabel(physicalState)
        TwinRackPresentation.EXPECTED -> location.expectedPalletCode ?: "VACÍO"
        TwinRackPresentation.OBSERVED -> observedPalletLabel(location)
    }
    Box(
        modifier = modifier
            .height(110.dp)
            .animateContentSize()
            .background(background, RoundedCornerShape(8.dp))
            .border(if (isSelected || isTarget) 2.dp else 1.dp, borderColor, RoundedCornerShape(8.dp))
            .clickable(onClick = onClick)
            .padding(9.dp),
    ) {
        Column(Modifier.fillMaxSize()) {
            Text(location.code, color = AeroTwinColors.TextPrimary, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 11.sp)
            Spacer(Modifier.height(5.dp))
            Text(
                primary,
                color = if (presentation == TwinRackPresentation.PHYSICAL) twinStateColor(physicalState) else AeroTwinColors.TextPrimary,
                fontWeight = FontWeight.Bold,
                fontSize = 11.sp,
                maxLines = 2,
            )
            if (presentation == TwinRackPresentation.PHYSICAL && location.badges.isNotEmpty()) {
                Spacer(Modifier.height(5.dp))
                Text(
                    location.badges.take(2).joinToString(" · ") { operationalLabel(it) },
                    color = AeroTwinColors.TextSecondary,
                    fontSize = 9.sp,
                    maxLines = 1,
                )
            }
            if (isTarget) {
                Spacer(Modifier.weight(1f))
                Text("OBJETIVO", color = AeroTwinColors.Info, fontSize = 9.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun TwinPositionDetail(location: LiveLocationDto, viewModel: AeroTwinViewModel) {
    val physicalState = location.physicalState ?: location.result ?: "UNINSPECTED"
    SectionHeader("Detalle de posición")
    Spacer(Modifier.height(8.dp))
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(AeroTwinColors.Surface, RoundedCornerShape(10.dp))
            .border(1.dp, AeroTwinColors.Border, RoundedCornerShape(10.dp))
            .padding(16.dp),
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
            Column(Modifier.weight(1f)) {
                Text(location.code, color = AeroTwinColors.TextPrimary, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 22.sp)
                Text(location.product ?: "Producto no asociado", color = AeroTwinColors.TextPrimary, fontWeight = FontWeight.SemiBold)
                location.sku?.let { Text(it, color = AeroTwinColors.TextSecondary, fontFamily = FontFamily.Monospace, fontSize = 12.sp) }
            }
            StatusBadge(twinPhysicalLabel(physicalState), twinStateTone(physicalState))
        }
        Spacer(Modifier.height(14.dp))
        Text("Esperado", color = AeroTwinColors.TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.Bold)
        Text(location.expectedPalletCode ?: "Vacío esperado", color = AeroTwinColors.TextPrimary, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(10.dp))
        Text("Observado", color = AeroTwinColors.TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.Bold)
        Text(observedPalletLabel(location), color = AeroTwinColors.TextPrimary, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(10.dp))
        Text("Resultado: ${operationalLabel(location.comparisonResult ?: location.result)}", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
        val expectedQuantity = location.expectedQuantity?.toString() ?: "—"
        val observedQuantity = location.observedQuantity?.toString() ?: "—"
        Text("Cantidad esperada: $expectedQuantity", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
        Text("Cantidad asociada al pallet en WMS: $observedQuantity", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
        location.lot?.let { Text("Lote: $it", color = AeroTwinColors.TextSecondary, fontSize = 13.sp) }
        location.daysToExpiry?.let { Text("Caduca en: $it días", color = AeroTwinColors.TextSecondary, fontSize = 13.sp) }
        location.rotation?.let { Text("Rotación: $it", color = AeroTwinColors.TextSecondary, fontSize = 13.sp) }
        location.coverageDays?.let { Text("Cobertura: ${it.formatCompact()} días", color = AeroTwinColors.TextSecondary, fontSize = 13.sp) }
        if (location.fefoRisk == true) Text("Riesgo FEFO", color = AeroTwinColors.Warning, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
        if ((location.riskScore ?: 0) > 0) {
            Spacer(Modifier.height(10.dp))
            Text("Risk Score ${location.riskScore} · ${agentSeverityLabel(location.severity ?: "LOW")}", color = AeroTwinColors.Primary, fontWeight = FontWeight.Bold)
        }
        if (location.badges.isNotEmpty()) {
            Spacer(Modifier.height(10.dp))
            Text("Señales: ${location.badges.joinToString(" · ") { operationalLabel(it) }}", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
        }
        location.lossPreventionReason?.let { reason ->
            Spacer(Modifier.height(10.dp))
            StateBanner(location.lossPreventionSignal ?: "Señal preventiva", reason, AeroStatusTone.WARNING)
        }
        location.slottingSuggestion?.let { suggestion ->
            Spacer(Modifier.height(10.dp))
            StateBanner("Sugerencia de slotting", suggestion, AeroStatusTone.INFO)
        }
        Spacer(Modifier.height(14.dp))
        if (location.exceptionId != null) {
            SecondaryAction("VER EXCEPCIÓN", { viewModel.openExceptionDetail(location.exceptionId) })
        } else if (location.id != null) {
            SecondaryAction("VER HISTORIAL", { viewModel.openLocationHistory(location.id) })
        }
    }
}

@Composable
private fun TwinStateLegend() {
    Text(
        "Gris sin inspeccionar · azul analizando · verde correcto · rojo discrepancia · ámbar revisión",
        color = AeroTwinColors.TextSecondary,
        fontSize = 11.sp,
    )
}

private fun twinRows(locations: List<LiveLocationDto>): List<List<LiveLocationDto>> =
    locations.groupBy(::twinRowIndex)
        .toSortedMap()
        .values
        .map { it.sortedBy(::twinColumnIndex) }

private fun twinRowIndex(location: LiveLocationDto): Int = location.rowIndex ?: location.code.split("-").getOrNull(1)?.toIntOrNull() ?: Int.MAX_VALUE
private fun twinColumnIndex(location: LiveLocationDto): Int = location.columnIndex ?: location.code.split("-").getOrNull(2)?.toIntOrNull() ?: Int.MAX_VALUE

private fun observedPalletLabel(location: LiveLocationDto): String = location.observedPalletCode ?: when (location.comparisonResult ?: location.result) {
    "CORRECT_EMPTY", "EXPECTED_PALLET_MISSING" -> "Vacío confirmado"
    "UNRESOLVED", "HUMAN_REVIEW_REQUIRED" -> "No resuelto"
    else -> "Sin lectura final"
}

private fun twinPhysicalLabel(state: String): String = when (state.uppercase()) {
    "UNINSPECTED", "PENDING" -> "SIN INSPECCIONAR"
    "SCANNING", "ANALYZING", "ANALISING" -> "ANALIZANDO"
    "CORRECT", "ACCEPTED", "CORRECT_EMPTY" -> "CORRECTO"
    "REVIEW_REQUIRED", "HUMAN_REVIEW_REQUIRED", "UNRESOLVED" -> "REVISIÓN"
    "DISCREPANCY", "PALLET_MISMATCH", "EXPECTED_PALLET_MISSING", "UNEXPECTED_PALLET" -> "DISCREPANCIA"
    else -> operationalLabel(state).uppercase()
}

private fun twinStateTone(state: String): AeroStatusTone = when (state.uppercase()) {
    "CORRECT", "ACCEPTED", "CORRECT_EMPTY" -> AeroStatusTone.SUCCESS
    "REVIEW_REQUIRED", "HUMAN_REVIEW_REQUIRED", "UNRESOLVED" -> AeroStatusTone.WARNING
    "DISCREPANCY", "PALLET_MISMATCH", "EXPECTED_PALLET_MISSING", "UNEXPECTED_PALLET" -> AeroStatusTone.CRITICAL
    "SCANNING", "ANALYZING", "ANALISING" -> AeroStatusTone.INFO
    else -> AeroStatusTone.NEUTRAL
}

private fun twinStateColor(state: String): Color = when (twinStateTone(state)) {
    AeroStatusTone.SUCCESS -> AeroTwinColors.Success
    AeroStatusTone.WARNING -> AeroTwinColors.Warning
    AeroStatusTone.CRITICAL -> AeroTwinColors.Critical
    AeroStatusTone.INFO -> AeroTwinColors.Info
    AeroStatusTone.NEUTRAL -> AeroTwinColors.Pending
}

private fun twinStateBackground(state: String): Color = when (twinStateTone(state)) {
    AeroStatusTone.SUCCESS -> AeroTwinColors.SuccessSoft
    AeroStatusTone.WARNING -> AeroTwinColors.WarningSoft
    AeroStatusTone.CRITICAL -> AeroTwinColors.CriticalSoft
    AeroStatusTone.INFO -> AeroTwinColors.InfoSoft
    AeroStatusTone.NEUTRAL -> AeroTwinColors.SurfaceSubtle
}

private fun Double.formatPercent(): String = if (this % 1.0 == 0.0) toInt().toString() else "%.1f".format(this)
private fun Double.formatCompact(): String = if (this % 1.0 == 0.0) toInt().toString() else "%.1f".format(this)

@Composable
private fun AgentPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    var question by remember { mutableStateOf("") }
    Screen {
        AeroTopBar("Agente AeroTwin", "Asistente operativo", "Consulta datos reales del inventario.", showBack = true, onBack = viewModel::loadHome)
        Spacer(Modifier.height(20.dp))
        listOf("¿Qué debo revisar primero?", "¿Qué cambió desde ayer?", "¿Qué vence en 30 días?", "¿Hay riesgo FEFO?", "¿Qué ubicación repite más errores?").forEach { quick ->
            SecondaryAction(quick, { viewModel.askAgent(quick) }); Spacer(Modifier.height(8.dp))
        }
        Spacer(Modifier.height(14.dp)); OutlinedTextField(value=question,onValueChange={question=it},modifier=Modifier.fillMaxWidth(),label={Text("Consulta operativa")},shape=RoundedCornerShape(8.dp))
        Spacer(Modifier.height(10.dp)); ActionButton("CONSULTAR", { viewModel.askAgent(question) }, enabled=!state.loading)
        if (state.loading) { Spacer(Modifier.height(16.dp)); LoadingState("Consultando AeroTwin Core") }
        state.agentResponse?.let { response ->
            Spacer(Modifier.height(20.dp))
            StateBanner(
                agentIntentLabel(response.intent),
                response.answer,
                if (response.intent == "READ_ONLY_DENIED" || response.intent == "UNKNOWN") AeroStatusTone.WARNING else AeroStatusTone.INFO,
            )
            Spacer(Modifier.height(14.dp))
            StructuredAgentResponse(response, viewModel)
            AgentActions(response, viewModel)
        }
        ErrorMessage(state.error)
    }
}

@Composable
private fun LocationHistoryPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    val memory = state.locationMemory
    Screen {
        AeroTopBar("Historial", memory.string("code") ?: "Ubicación", "Memoria operacional derivada de lecturas finales.", showBack = true, onBack = viewModel::backFromLocationHistory)
        Spacer(Modifier.height(20.dp))
        if (state.loading) LoadingState("Cargando historial")
        memory?.let { item ->
            val risk = item.integer("last_risk_score") ?: 0
            val severity = item.string("last_severity", "severity") ?: "LOW"
            MetricTile("Riesgo actual", "$risk · ${agentSeverityLabel(severity)}", comparisonLabel(item.string("last_comparison_result") ?: "UNRESOLVED"))
            Spacer(Modifier.height(16.dp))
            val streak = item.integer("consecutive_anomalous_inspections") ?: 0
            val family = item.string("recurrent_anomaly_type")
            StateBanner(
                if (streak >= 2) "Anomalía recurrente" else "Sin racha recurrente",
                if (streak >= 2) "$streak inspecciones consecutivas · ${operationalLabel(family)}" else "La condición actual no forma una racha repetida.",
                if (streak >= 2) AeroStatusTone.WARNING else AeroStatusTone.NEUTRAL,
            )
            Spacer(Modifier.height(18.dp))
            SectionHeader("Estado físico actual")
            Spacer(Modifier.height(8.dp))
            Text(
                "Esperado: ${item.string("expected_pallet", "expected_pallet_code") ?: "—"}\n" +
                    "Observado: ${item.string("last_observed_pallet", "observed_pallet") ?: stateLabel(item.string("reading_status"))}\n" +
                    "Producto: ${item.string("product") ?: "—"}${item.string("sku")?.let { " · $it" } ?: ""}\n" +
                    "Lote: ${item.string("lot") ?: "—"}",
                color = AeroTwinColors.TextPrimary,
            )
            Spacer(Modifier.height(14.dp))
            val lastValid = item.objectValue("last_valid_reading")
            StateBanner(
                "Última lectura válida",
                lastValid?.string("observed_pallet", "pallet", "observed_pallet_code")
                    ?: item.string("last_valid_reading")?.let { "Lectura #$it" }
                    ?: "No existe una lectura ACCEPTED anterior.",
                AeroStatusTone.INFO,
            )
            item.objectValue("latest_evidence")?.let { evidence ->
                Spacer(Modifier.height(14.dp))
                StateBanner(
                    "Última evidencia",
                    "Evidencia #${evidence.integer("evidence_id", "id") ?: "—"} · ${humanDate(evidence.string("captured_at", "created_at"))}",
                    AeroStatusTone.INFO,
                )
            }
            item.boolean("fefo_risk")?.takeIf { it }?.let {
                Spacer(Modifier.height(14.dp))
                StateBanner("Riesgo FEFO", "Existe una prioridad de salida con vencimiento anterior.", AeroStatusTone.WARNING)
            }
            Spacer(Modifier.height(22.dp))
            SectionHeader("Timeline de lecturas finales")
            Spacer(Modifier.height(10.dp))
            val timeline = item.arrayValues("timeline").mapNotNull { it.asObjectOrNull() }
            if (timeline.isEmpty()) {
                StateBanner("Sin lecturas finales", "No hay historial físico final para esta ubicación.", AeroStatusTone.NEUTRAL)
            } else {
                timeline.forEach { entry ->
                    LocationTimelineEntry(entry)
                    Spacer(Modifier.height(10.dp))
                }
            }
            Spacer(Modifier.height(18.dp))
            SectionHeader("Cambios recientes")
            Spacer(Modifier.height(8.dp))
            val changes = item.arrayValues("recent_changes").mapNotNull { it.asObjectOrNull() }
            if (changes.isEmpty()) {
                Text("Sin cambios FlowTwin recientes.", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
            } else {
                changes.forEach { change ->
                    Text("${operationalLabel(change.string("type", "change_type"))} · ${humanDate(change.string("created_at", "inspection_date"))}", color = AeroTwinColors.TextPrimary)
                    Spacer(Modifier.height(6.dp))
                }
            }
        }
        ErrorMessage(state.error)
    }
}

@Composable
private fun EvidencePage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    Screen {
        AeroTopBar("Evidencia", state.agentEvidenceId?.let { "Evidencia #$it" } ?: "Evidencia de lectura", "Activo de solo lectura vinculado por el Agente.", showBack = true, onBack = viewModel::backFromEvidence)
        Spacer(Modifier.height(20.dp))
        if (state.loading) LoadingState("Cargando evidencia")
        state.agentEvidence?.let { frame ->
            Image(
                bitmap = frame.asImageBitmap(),
                contentDescription = "Evidencia de lectura",
                contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxWidth().height(420.dp).background(AeroTwinColors.PrimaryDark, RoundedCornerShape(8.dp)),
            )
        }
        if (!state.loading && state.agentEvidence == null && state.error == null) {
            StateBanner("Evidencia no disponible", "AeroTwin no recibió una imagen válida para esta evidencia.", AeroStatusTone.NEUTRAL)
        }
        ErrorMessage(state.error)
    }
}

@Composable
private fun StructuredAgentResponse(response: com.twobit.aerotwin.data.api.AgentResponseDto, viewModel: AeroTwinViewModel) {
    val records = agentRows(response.data)
    when (response.intent) {
        "PRIORITY" -> {
            SectionHeader("Prioridades operativas")
            records.forEach { row -> AgentPriorityCard(row) }
        }
        "EXPIRY" -> {
            SectionHeader("Lotes próximos a vencer")
            records.forEach { row -> AgentExpiryCard(row) }
        }
        "FEFO" -> {
            SectionHeader("Riesgo FEFO")
            records.forEach { row -> AgentFefoCard(row) }
        }
        "LOW_COVERAGE" -> {
            SectionHeader("Cobertura baja")
            records.forEach { row -> AgentCoverageCard(row) }
        }
        "RECURRENT" -> {
            SectionHeader("Ubicaciones recurrentes")
            records.forEach { row -> AgentRecurringCard(row) }
        }
        "LOCATION_STATUS" -> AgentLocationStatus(response.data.asObjectOrNull())
        "LOCATION_HISTORY" -> AgentHistorySummary(response.data.asObjectOrNull())
        "RECENT_CHANGES" -> {
            SectionHeader("Cambios detectados")
            records.forEach { row -> AgentChangeCard(row) }
        }
        "UNRESOLVED" -> {
            SectionHeader("Lecturas no resueltas")
            records.forEach { row -> AgentUnresolvedCard(row) }
        }
        "COMPARE_ZONES" -> {
            SectionHeader("Comparación por zona")
            records.forEach { row -> AgentZoneCard(row) }
        }
        "LATEST_EVIDENCE" -> AgentLatestEvidence(response.data.asObjectOrNull())
        "INSPECTION_COVERAGE" -> AgentInspectionCoverage(response.data.asObjectOrNull())
    }
}

@Composable
private fun AgentPriorityCard(row: JsonObject) = AgentCard {
    val location = row.string("location", "location_code", "code") ?: row.integer("location_id")?.let { "Ubicación #$it" } ?: "Ubicación"
    Text(location, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
    Text(operationalLabel(row.string("title", "type", "exception_type")), color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
    AgentRiskLine(row)
}

@Composable
private fun AgentExpiryCard(row: JsonObject) = AgentCard {
    Text(row.string("product", "product_name", "sku") ?: "Producto sin identificar", fontWeight = FontWeight.Bold)
    Text("Lote ${row.string("lot", "lot_code") ?: "—"}", fontFamily = FontFamily.Monospace, color = AeroTwinColors.TextSecondary)
    row.integer("days_to_expiry", "days_remaining")?.let { Text("Caduca en $it días", color = AeroTwinColors.Warning, fontWeight = FontWeight.Bold) }
}

@Composable
private fun AgentFefoCard(row: JsonObject) = AgentCard {
    Text("Lote actual: ${row.string("lot", "current_lot", "lot_code") ?: "—"}", fontWeight = FontWeight.Bold)
    Text("Preferido: ${row.string("preferred_lot", "fefo_lot", "earliest_lot") ?: "—"}", fontFamily = FontFamily.Monospace, color = AeroTwinColors.TextSecondary)
    row.string("reason", "fefo_reason")?.let { Text(it, color = AeroTwinColors.TextSecondary, fontSize = 13.sp) }
}

@Composable
private fun AgentCoverageCard(row: JsonObject) = AgentCard {
    Text(row.string("product", "product_name", "sku") ?: "Producto sin identificar", fontWeight = FontWeight.Bold)
    row.numberText("coverage_days")?.let { Text("$it días de cobertura", color = AeroTwinColors.Warning, fontWeight = FontWeight.Bold) }
    Text("Rotación ${row.string("rotation", "rotation_level") ?: "—"}${row.string("location", "location_code")?.let { " · $it" } ?: ""}", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
    AgentRiskLine(row)
}

@Composable
private fun AgentRecurringCard(row: JsonObject) = AgentCard {
    Text(row.string("location", "location_code", "code") ?: "Ubicación", fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
    Text(operationalLabel(row.string("recurrent_anomaly_type", "type", "exception_type")), color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
    row.integer("consecutive_anomalous_inspections", "streak")?.let { Text("$it inspecciones consecutivas", color = AeroTwinColors.Warning, fontWeight = FontWeight.Bold) }
    AgentRiskLine(row)
}

@Composable
private fun AgentLocationStatus(data: JsonObject?) {
    val memory = data?.objectValue("memory") ?: data ?: return
    SectionHeader("Estado de ubicación")
    Spacer(Modifier.height(8.dp))
    AgentCard {
        Text(memory.string("code", "location", "location_code") ?: "Ubicación", fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
        Text("Esperado: ${memory.string("expected_pallet", "expected_pallet_code") ?: "—"}")
        Text("Observado: ${memory.string("last_observed_pallet", "observed_pallet") ?: stateLabel(memory.string("reading_status"))}")
        AgentRiskLine(memory)
        memory.string("product")?.let { product -> Text("$product${memory.string("sku")?.let { " · $it" } ?: ""} · Lote ${memory.string("lot") ?: "—"}", color = AeroTwinColors.TextSecondary, fontSize = 13.sp) }
        memory.numberText("coverage_days")?.let { Text("Cobertura: $it días${if (memory.boolean("fefo_risk") == true) " · Riesgo FEFO" else ""}", color = AeroTwinColors.TextSecondary, fontSize = 13.sp) }
        memory.integer("consecutive_anomalous_inspections")?.takeIf { it >= 2 }?.let { Text("Esta condición se repite en $it inspecciones consecutivas.", color = AeroTwinColors.Warning, fontSize = 13.sp, fontWeight = FontWeight.SemiBold) }
        memory.objectValue("risk_breakdown")?.let { breakdown ->
            val lines = breakdown.entrySet().joinToString(" · ") { "+${it.value.asString} ${operationalLabel(it.key)}" }
            if (lines.isNotBlank()) Text("Razones: $lines", color = AeroTwinColors.TextSecondary, fontSize = 12.sp)
        }
    }
}

@Composable
private fun AgentHistorySummary(data: JsonObject?) {
    val memory = data?.objectValue("memory")
    val timeline = data?.arrayValues("timeline")?.mapNotNull { it.asObjectOrNull() }.orEmpty()
    SectionHeader("Historial de ubicación")
    memory?.let { AgentLocationStatus(it) }
    timeline.take(3).forEach { entry -> LocationTimelineEntry(entry) }
}

@Composable
private fun AgentChangeCard(row: JsonObject) = AgentCard {
    Text(row.string("location", "location_code", "code") ?: row.integer("location_id")?.let { "Ubicación #$it" } ?: "Ubicación", fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
    Text(operationalLabel(row.string("type", "change_type")), color = AeroTwinColors.Primary, fontSize = 13.sp, fontWeight = FontWeight.Bold)
    Text("${readingValue(row.string("previous", "before"))}  →  ${readingValue(row.string("current", "after"))}", fontFamily = FontFamily.Monospace)
    AgentRiskLine(row)
}

@Composable
private fun AgentUnresolvedCard(row: JsonObject) = AgentCard {
    Text(row.string("location", "location_code", "code") ?: "Ubicación", fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
    Text("No resuelto · ${row.integer("attempts", "attempt_number") ?: 0} intento(s)", color = AeroTwinColors.Warning, fontWeight = FontWeight.Bold)
    row.numberText("quality", "quality_score")?.let { Text("Calidad: $it", color = AeroTwinColors.TextSecondary, fontSize = 13.sp) }
    row.string("reason", "reading_status", "comparison_result")?.let { Text(operationalLabel(it), color = AeroTwinColors.TextSecondary, fontSize = 13.sp) }
}

@Composable
private fun AgentZoneCard(row: JsonObject) = AgentCard {
    Text(row.string("zone_code", "code", "zone") ?: "Zona", fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
    Text("Riesgo promedio ${row.numberText("average_risk", "avg_risk") ?: "—"} · máximo ${row.numberText("max_risk") ?: "—"}", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
    Text("Abiertas ${row.integer("open_exceptions") ?: 0} · No resueltas ${row.integer("unresolved_locations", "unresolved") ?: 0}", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
}

@Composable
private fun AgentLatestEvidence(data: JsonObject?) {
    if (data == null) return
    SectionHeader("Última evidencia")
    Spacer(Modifier.height(8.dp))
    AgentCard {
        Text(data.string("location", "location_code") ?: "Evidencia de ubicación", fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
        Text("Evidencia #${data.integer("evidence_id", "id") ?: "—"} · ${humanDate(data.string("captured_at", "created_at"))}", color = AeroTwinColors.TextSecondary)
        data.string("mime_type", "evidence_type")?.let { Text(it, color = AeroTwinColors.TextSecondary, fontSize = 13.sp) }
    }
}

@Composable
private fun AgentInspectionCoverage(data: JsonObject?) {
    if (data == null) return
    SectionHeader("Cobertura de inspección")
    Spacer(Modifier.height(8.dp))
    MetricTile(
        "${data.string("zone_code", "zone") ?: "Zona"}",
        "${data.integer("completed_locations", "completed") ?: 0} / ${data.integer("total_locations", "total") ?: 0}",
        "${data.numberText("coverage_percent") ?: "0"}% · ${data.integer("pending") ?: 0} pendientes",
    )
}

@Composable
private fun AgentRiskLine(row: JsonObject) {
    row.integer("risk_score", "last_risk_score")?.let { score ->
        val severity = row.string("severity", "last_severity") ?: "LOW"
        Spacer(Modifier.height(4.dp))
        StatusBadge("Riesgo $score · ${agentSeverityLabel(severity)}", agentSeverityTone(severity))
    }
}

@Composable
private fun AgentCard(content: @Composable () -> Unit) {
    Spacer(Modifier.height(8.dp))
    Column(
        modifier = Modifier.fillMaxWidth().background(AeroTwinColors.Surface, RoundedCornerShape(8.dp)).border(1.dp, AeroTwinColors.Border, RoundedCornerShape(8.dp)).padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) { content() }
}

@Composable
private fun AgentActions(response: com.twobit.aerotwin.data.api.AgentResponseDto, viewModel: AeroTwinViewModel) {
    response.actions.forEach { action ->
        val onClick: (() -> Unit)? = when (action.type) {
            "OPEN_EXCEPTION" -> action.id?.let { id -> { viewModel.openExceptionDetail(id) } }
            "OPEN_LOCATION_HISTORY" -> action.id?.let { id -> { viewModel.openLocationHistory(id) } }
            "OPEN_FLOWTWIN" -> viewModel::openFlowTwinChanges
            "OPEN_EVIDENCE" -> action.id?.let { id -> { viewModel.openEvidence(id) } }
            "OPEN_SENSOR_MONITOR" -> viewModel::openSensorMonitorFromAgent
            else -> null
        }
        val label = when (action.type) {
            "OPEN_EXCEPTION" -> "VER EXCEPCIÓN"
            "OPEN_LOCATION_HISTORY" -> "VER HISTORIAL"
            "OPEN_FLOWTWIN" -> "VER CAMBIOS"
            "OPEN_EVIDENCE" -> "VER EVIDENCIA"
            "OPEN_SENSOR_MONITOR" -> "MONITOREAR SENSORES"
            else -> null
        }
        if (onClick != null && label != null) {
            Spacer(Modifier.height(10.dp))
            SecondaryAction(label, onClick)
        }
    }
}

@Composable
private fun LocationTimelineEntry(entry: JsonObject) {
    val score = entry.integer("risk_score") ?: 0
    val severity = entry.string("severity") ?: "LOW"
    val comparison = entry.string("comparison_result") ?: "UNRESOLVED"
    AgentCard {
        Text(humanDate(entry.string("completed_at", "inspection_date", "created_at")), color = AeroTwinColors.TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Bold)
        Text(observedReadingLabel(entry), fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
        Text(operationalLabel(comparison), color = if (comparison in setOf("CORRECT", "CORRECT_EMPTY")) AeroTwinColors.Success else AeroTwinColors.TextPrimary)
        Text("Esperado: ${entry.string("expected_pallet", "expected_pallet_code") ?: "—"} · ${stateLabel(entry.string("reading_status"))}", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
        if (score > 0) StatusBadge("$score · ${agentSeverityLabel(severity)}", agentSeverityTone(severity))
        entry.string("exception_type")?.let { Text("Excepción: ${operationalLabel(it)}", color = AeroTwinColors.TextSecondary, fontSize = 12.sp) }
        entry.objectValue("flowtwin_change")?.let { change -> Text("Cambio: ${operationalLabel(change.string("type"))}", color = AeroTwinColors.Primary, fontSize = 12.sp) }
        entry.integer("evidence_id")?.let { Text("Evidencia #$it", color = AeroTwinColors.TextSecondary, fontSize = 12.sp) }
    }
}

private fun JsonElement?.asObjectOrNull(): JsonObject? =
    if (this != null && !isJsonNull && isJsonObject) asJsonObject else null

private fun JsonObject?.element(name: String): JsonElement? =
    this?.get(name)?.takeUnless { it.isJsonNull }

private fun JsonObject?.string(vararg names: String): String? = names.asSequence()
    .mapNotNull { name -> element(name)?.takeIf { it.isJsonPrimitive }?.let { runCatching { it.asString }.getOrNull() } }
    .map { it.trim() }
    .firstOrNull { it.isNotBlank() && it != "null" }

private fun JsonObject?.integer(vararg names: String): Int? =
    string(*names)?.toDoubleOrNull()?.toInt()

private fun JsonObject?.numberText(vararg names: String): String? = string(*names)?.let { value ->
    value.toDoubleOrNull()?.let { number -> if (number % 1.0 == 0.0) number.toInt().toString() else "%.1f".format(number) } ?: value
}

private fun JsonObject?.boolean(vararg names: String): Boolean? = string(*names)?.toBooleanStrictOrNull()

private fun JsonObject?.objectValue(name: String): JsonObject? = element(name).asObjectOrNull()

private fun JsonObject?.arrayValues(name: String): List<JsonElement> = element(name)
    ?.takeIf { it.isJsonArray }
    ?.asJsonArray
    ?.map { it }
    .orEmpty()

private fun agentRows(data: JsonElement): List<JsonObject> {
    if (data.isJsonArray) return data.asJsonArray.mapNotNull { it.asObjectOrNull() }
    val objectValue = data.asObjectOrNull() ?: return emptyList()
    val nested = listOf("items", "results", "rows").firstNotNullOfOrNull { key ->
        objectValue.element(key)?.takeIf { it.isJsonArray }
    }
    return nested?.asJsonArray?.mapNotNull { it.asObjectOrNull() } ?: listOf(objectValue)
}

private fun agentIntentLabel(intent: String): String = when (intent) {
    "PRIORITY" -> "Prioridad operativa"
    "EXPIRY" -> "Próximos vencimientos"
    "FEFO" -> "Riesgo FEFO"
    "LOW_COVERAGE" -> "Cobertura baja"
    "RECURRENT" -> "Anomalías recurrentes"
    "LOCATION_STATUS" -> "Estado de ubicación"
    "LOCATION_HISTORY" -> "Historial de ubicación"
    "RECENT_CHANGES" -> "Cambios recientes"
    "UNRESOLVED" -> "Lecturas no resueltas"
    "COMPARE_ZONES" -> "Comparación de zonas"
    "LATEST_EVIDENCE" -> "Última evidencia"
    "INSPECTION_COVERAGE" -> "Cobertura de inspección"
    "READ_ONLY_DENIED" -> "Consulta de solo lectura"
    "UNKNOWN" -> "Información insuficiente"
    else -> intent.replace('_', ' ')
}

private fun operationalLabel(value: String?): String = when (value) {
    "PALLET_MISMATCH" -> "Pallet diferente"
    "EXPECTED_PALLET_MISSING" -> "Falta pallet esperado"
    "UNEXPECTED_PALLET" -> "Pallet no esperado"
    "PALLET_CHANGED" -> "Pallet cambió"
    "PALLET_ADDED" -> "Pallet apareció"
    "PALLET_REMOVED" -> "Pallet retirado"
    "BECAME_UNRESOLVED" -> "Se volvió no resuelto"
    "RESOLVED_SINCE_PREVIOUS" -> "Resuelto desde la inspección anterior"
    "PERSISTENT_DISCREPANCY" -> "Discrepancia persistente"
    "CORRECT", "CORRECT_EMPTY" -> "Correcto"
    "UNRESOLVED", "HUMAN_REVIEW_REQUIRED" -> "No resuelto"
    null -> "—"
    else -> value.replace('_', ' ')
}

private fun agentSeverityLabel(value: String): String = when (value) {
    "CRITICAL" -> "CRÍTICO"
    "HIGH" -> "ALTO"
    "MEDIUM" -> "MEDIO"
    "LOW" -> "BAJO"
    else -> value
}

private fun agentSeverityTone(value: String): AeroStatusTone = when (value) {
    "CRITICAL", "HIGH" -> AeroStatusTone.CRITICAL
    "MEDIUM" -> AeroStatusTone.WARNING
    "LOW" -> AeroStatusTone.INFO
    else -> AeroStatusTone.NEUTRAL
}

private fun stateLabel(value: String?): String = when (value) {
    "HUMAN_REVIEW_REQUIRED", "UNRESOLVED" -> "No resuelto"
    "ACCEPTED" -> "Lectura aceptada"
    "RESCAN_REQUIRED" -> "ReScan requerido"
    else -> "—"
}

private fun readingValue(value: String?): String = value?.takeIf { it.isNotBlank() } ?: "—"

private fun observedReadingLabel(row: JsonObject): String {
    row.string("observed_pallet", "observed_pallet_code")?.let { return it }
    val comparison = row.string("comparison_result")
    return when {
        comparison in setOf("CORRECT_EMPTY", "EXPECTED_PALLET_MISSING") -> "Vacío confirmado"
        comparison == "UNRESOLVED" || row.string("reading_status") == "HUMAN_REVIEW_REQUIRED" -> "No resuelto"
        else -> "—"
    }
}

private fun humanDate(value: String?): String {
    if (value.isNullOrBlank()) return "Fecha no disponible"
    val date = value.take(10)
    if (date.length != 10 || date[4] != '-' || date[7] != '-') return value
    val month = when (date.substring(5, 7)) {
        "01" -> "Ene"; "02" -> "Feb"; "03" -> "Mar"; "04" -> "Abr"; "05" -> "May"; "06" -> "Jun"
        "07" -> "Jul"; "08" -> "Ago"; "09" -> "Sep"; "10" -> "Oct"; "11" -> "Nov"; "12" -> "Dic"
        else -> return date
    }
    return "${date.substring(8, 10)} $month"
}

@Composable
private fun FlowTwinChangesPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState; val flow = state.flowTwin
    Screen {
        AeroTopBar("¿Qué cambió?", "Desde la última inspección", "Comparación temporal de lecturas finales.", showBack = true, onBack = viewModel::loadHome)
        Spacer(Modifier.height(20.dp))
        if (state.loading) LoadingState("Comparando inspecciones")
        flow?.let {
            if (it.status == "NO_PREVIOUS_INSPECTION") StateBanner("Sin inspección anterior", "AeroTwin necesita una inspección completada previa de la misma zona.", AeroStatusTone.NEUTRAL)
            else {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Box(Modifier.weight(1f)) { MetricTile("Sin cambios", "${it.summary.unchanged}") }
                    Box(Modifier.weight(1f)) { MetricTile("Cambios", "${it.summary.changed}", "${it.summary.persistent} persistentes") }
                }
                Spacer(Modifier.height(20.dp))
                it.changes.forEach { change ->
                    SectionHeader(change.location); Spacer(Modifier.height(6.dp))
                    Text(if (change.type == "PALLET_ADDED") "PALLET APARECIÓ" else change.type.replace('_', ' '), color = AeroTwinColors.Primary, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(8.dp)); Text("ANTES\n${change.previous}\n\nAHORA\n${change.current}", color = AeroTwinColors.TextPrimary, fontFamily = FontFamily.Monospace)
                    if (change.riskScore > 0) { Spacer(Modifier.height(8.dp)); Text("Riesgo ${change.riskScore}", color = AeroTwinColors.TextSecondary) }
                    change.exceptionId?.let { id -> Spacer(Modifier.height(10.dp)); SecondaryAction("VER DETALLE", { viewModel.openExceptionDetail(id) }) }
                    Spacer(Modifier.height(20.dp)); AeroDivider(); Spacer(Modifier.height(16.dp))
                }
            }
        }
        ErrorMessage(state.error)
    }
}

@Composable
private fun ExceptionsPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    val applied = state.exceptionFilters
    var typeMenuOpen by remember { mutableStateOf(false) }
    var severityMenuOpen by remember { mutableStateOf(false) }
    var zoneDraft by remember(applied.zone) { mutableStateOf(applied.zone.orEmpty()) }
    var lotDraft by remember(applied.lot) { mutableStateOf(applied.lot.orEmpty()) }
    var qualityDraft by remember(applied.qualityMax) { mutableStateOf(applied.qualityMax?.toString().orEmpty()) }
    val typeOptions = listOf(
        null to "TODOS LOS TIPOS",
        "PALLET_MISMATCH" to "PALLET DIFERENTE",
        "PALLET_MISSING" to "PALLET FALTANTE",
        "UNEXPECTED_PALLET" to "PALLET INESPERADO",
        "EXPIRING_SOON" to "PRÓXIMO A VENCER",
        "LOW_COVERAGE" to "COBERTURA BAJA",
        "FEFO_RISK" to "RIESGO FEFO",
        "LOW_QUALITY" to "CALIDAD BAJA",
        "HISTORICAL_ANOMALY" to "ANOMALÍA HISTÓRICA",
    )
    val severityOptions = listOf(
        null to "TODAS",
        "LOW" to "BAJA",
        "MEDIUM" to "MEDIA",
        "HIGH" to "ALTA",
        "CRITICAL" to "CRÍTICA",
    )
    fun applyFilters(
        type: String? = applied.type,
        severity: String? = applied.severity,
        expiry: Boolean = applied.expiry,
    ) {
        viewModel.openExceptions(
            type = type,
            severity = severity,
            zone = zoneDraft,
            expiry = expiry,
            lot = lotDraft,
            qualityMax = qualityDraft.toIntOrNull(),
        )
    }
    Screen {
        AeroTopBar("Excepciones", "Prioridades operativas", "Ordenadas por Risk Score.", showBack = true, onBack = viewModel::loadHome)
        Spacer(Modifier.height(14.dp))
        SectionHeader("Filtros")
        Spacer(Modifier.height(8.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(Modifier.weight(1.25f)) {
                OutlinedButton(onClick = { typeMenuOpen = true }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(8.dp)) {
                    val selected = typeOptions.firstOrNull { it.first == applied.type }?.second ?: applied.type.orEmpty()
                    Text("TIPO: $selected", color = AeroTwinColors.TextPrimary, fontSize = 10.sp, fontWeight = FontWeight.Bold, maxLines = 1)
                }
                DropdownMenu(expanded = typeMenuOpen, onDismissRequest = { typeMenuOpen = false }) {
                    typeOptions.forEach { (value, label) ->
                        DropdownMenuItem(
                            text = { Text(label, fontSize = 13.sp) },
                            onClick = {
                                typeMenuOpen = false
                                applyFilters(type = value)
                            },
                        )
                    }
                }
            }
            Box(Modifier.weight(1.05f)) {
                OutlinedButton(onClick = { severityMenuOpen = true }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(8.dp)) {
                    val selected = severityOptions.firstOrNull { it.first == applied.severity }?.second ?: applied.severity.orEmpty()
                    Text("NIVEL: $selected", color = AeroTwinColors.TextPrimary, fontSize = 9.sp, fontWeight = FontWeight.Bold, maxLines = 1)
                }
                DropdownMenu(expanded = severityMenuOpen, onDismissRequest = { severityMenuOpen = false }) {
                    severityOptions.forEach { (value, label) ->
                        DropdownMenuItem(
                            text = { Text(label, fontSize = 13.sp) },
                            onClick = {
                                severityMenuOpen = false
                                applyFilters(severity = value)
                            },
                        )
                    }
                }
            }
            OutlinedButton(onClick = { applyFilters(expiry = !applied.expiry) }, modifier = Modifier.weight(0.65f), shape = RoundedCornerShape(8.dp)) {
                Text("VENCE", color = if (applied.expiry) AeroTwinColors.Primary else AeroTwinColors.TextSecondary, fontSize = 9.sp, fontWeight = FontWeight.Bold)
            }
        }
        Spacer(Modifier.height(8.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = zoneDraft,
                onValueChange = { zoneDraft = it.uppercase() },
                modifier = Modifier.weight(1f),
                label = { Text("Zona") },
                placeholder = { Text("A") },
                singleLine = true,
                textStyle = TextStyle(fontSize = 13.sp, fontFamily = FontFamily.Monospace),
                shape = RoundedCornerShape(8.dp),
            )
            OutlinedTextField(
                value = lotDraft,
                onValueChange = { lotDraft = it.uppercase() },
                modifier = Modifier.weight(1.35f),
                label = { Text("Lote") },
                placeholder = { Text("LOT-008") },
                singleLine = true,
                textStyle = TextStyle(fontSize = 13.sp, fontFamily = FontFamily.Monospace),
                shape = RoundedCornerShape(8.dp),
            )
        }
        Spacer(Modifier.height(8.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = qualityDraft,
                onValueChange = { qualityDraft = it.filter(Char::isDigit).take(3) },
                modifier = Modifier.weight(1f),
                label = { Text("Calidad máx.") },
                placeholder = { Text("≤ 70") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                textStyle = TextStyle(fontSize = 13.sp, fontFamily = FontFamily.Monospace),
                shape = RoundedCornerShape(8.dp),
            )
            OutlinedButton(
                onClick = { applyFilters() },
                modifier = Modifier.weight(0.8f).height(56.dp),
                shape = RoundedCornerShape(8.dp),
            ) {
                Text("APLICAR", color = AeroTwinColors.Primary, fontSize = 10.sp, fontWeight = FontWeight.Bold)
            }
            TextButton(onClick = {
                zoneDraft = ""
                lotDraft = ""
                qualityDraft = ""
                viewModel.openExceptions()
            }) { Text("LIMPIAR", color = AeroTwinColors.TextSecondary, fontSize = 10.sp, fontWeight = FontWeight.Bold) }
        }
        Spacer(Modifier.height(16.dp))
        if (state.loading) LoadingState("Cargando excepciones")
        if (!state.loading && state.exceptions.isEmpty()) StateBanner("Sin excepciones abiertas", "No hay casos pendientes para esta operación.", AeroStatusTone.SUCCESS, Icons.Outlined.CheckCircle)
        state.exceptions.forEach { item ->
            OutlinedButton(onClick = { viewModel.openExceptionDetail(item.id) }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(8.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Column { Text(item.location, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold); Text(item.type.replace('_', ' '), color = AeroTwinColors.TextSecondary, fontSize = 12.sp) }
                    StatusBadge("${item.riskScore} · ${item.severity}", if (item.severity == "CRITICAL") AeroStatusTone.CRITICAL else AeroStatusTone.WARNING)
                }
            }; Spacer(Modifier.height(10.dp))
        }
        ErrorMessage(state.error)
    }
}

@Composable
private fun ExceptionDetailPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState; val item = state.exceptionDetail
    Screen {
        AeroTopBar("Excepción", item?.location ?: "Detalle operativo", item?.shortReason, showBack = true, onBack = viewModel::backFromExceptionDetail)
        Spacer(Modifier.height(20.dp)); if (state.loading) LoadingState("Cargando contexto operativo")
        item?.let {
            MetricTile("Risk score", "${it.riskScore} · ${it.severity}", it.type.replace('_', ' ')); Spacer(Modifier.height(16.dp))
            SectionHeader("Comparación física"); Spacer(Modifier.height(8.dp)); Text("Esperado: ${it.expectedPallet ?: "—"}\nObservado: ${it.observedPallet ?: "—"}", color = AeroTwinColors.TextPrimary)
            Spacer(Modifier.height(18.dp)); SectionHeader("Inventario"); Spacer(Modifier.height(8.dp)); Text("${it.product ?: "Sin producto"} · ${it.sku ?: "—"}\nPallet ${it.pallet ?: "—"} · Lote ${it.lot ?: "—"}\nCantidad ${it.quantity ?: 0} · Caduca ${it.daysToExpiry ?: "—"} días\nRotación ${it.rotation ?: "—"} (${it.rotation30d ?: 0} en 30d) · Cobertura ${it.coverageDays ?: "—"} días\n${if (it.fefoRisk) "⚠ Riesgo FEFO: ${it.fefoReason ?: "requiere rotación FEFO"}" else "FEFO sin riesgo"}", color = AeroTwinColors.TextPrimary)
            Spacer(Modifier.height(18.dp)); SectionHeader("Risk breakdown"); Spacer(Modifier.height(8.dp)); Text(it.riskBreakdown.entries.joinToString("\n") { "+${it.value} ${it.key.replace('_', ' ')}" }, color = AeroTwinColors.TextPrimary)
            Spacer(Modifier.height(18.dp)); SectionHeader("Evidencias e intentos"); Spacer(Modifier.height(8.dp)); Text("Intento ${it.attemptNumber ?: "—"} · ${it.evidence.size} evidencias", color = AeroTwinColors.TextSecondary)
        }
        ErrorMessage(state.error)
    }
}

@Composable
private fun ActiveInspectionSummary(inspection: InspectionDto, lastReading: ReadingDto?, onContinue: () -> Unit) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(
            "INSPECCIÓN ACTIVA",
            color = AeroTwinColors.TextSecondary,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.9.sp,
        )
        StatusBadge("En curso", AeroStatusTone.INFO)
    }
    Spacer(Modifier.height(16.dp))
    OperationalCode("Zona", "ZONA ${inspection.zoneCode}", AeroTwinColors.PrimaryDark)
    Spacer(Modifier.height(18.dp))
    InspectionProgress(inspection.completedLocations, inspection.totalLocations)
    lastReading?.takeIf { it.inspectionId == inspection.id }?.let { reading ->
        Spacer(Modifier.height(26.dp))
        AeroDivider()
        Spacer(Modifier.height(18.dp))
        SectionHeader("Actividad reciente")
        Spacer(Modifier.height(10.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            OperationalCode("Última lectura", reading.locationCode)
            StatusBadge(readingStatusLabel(reading), resultTone(reading))
        }
    }
    Spacer(Modifier.height(28.dp))
    ActionButton("CONTINUAR INSPECCIÓN", onContinue, icon = Icons.AutoMirrored.Outlined.ArrowForward)
}

@Composable
private fun NoInspectionSummary(onStart: () -> Unit) {
    SectionHeader("Inspección")
    Spacer(Modifier.height(16.dp))
    StateBanner(
        title = "Sin inspección activa",
        message = "Selecciona una zona para iniciar una verificación física de posiciones.",
        tone = AeroStatusTone.NEUTRAL,
        icon = Icons.Outlined.Warehouse,
    )
    Spacer(Modifier.height(24.dp))
    ActionButton("SELECCIONAR ZONA", onStart, icon = Icons.AutoMirrored.Outlined.ArrowForward)
}

@Composable
private fun ZoneSelectionPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    Screen {
        AeroTopBar("Nueva inspección", "Selecciona una zona", "La inspección quedará asociada a tu sesión de operador.")
        Spacer(Modifier.height(28.dp))
        SectionHeader("Zonas disponibles")
        Spacer(Modifier.height(12.dp))
        if (state.loading) LoadingState("Consultando zonas activas")
        state.zones.forEach { zone ->
            ZoneOption(zone, !state.loading) { viewModel.createInspection(zone) }
            Spacer(Modifier.height(10.dp))
        }
        ErrorMessage(state.error)
        Spacer(Modifier.height(14.dp))
        TextButton(onClick = viewModel::backToHome) { Text("Volver a inicio", color = AeroTwinColors.TextSecondary) }
    }
}

@Composable
private fun ZoneOption(zone: ZoneDto, enabled: Boolean, onClick: () -> Unit) {
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier.fillMaxWidth().height(76.dp),
        shape = RoundedCornerShape(8.dp),
    ) {
        Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(zone.code, color = AeroTwinColors.Primary, fontFamily = FontFamily.Monospace, fontSize = 28.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f), horizontalAlignment = Alignment.Start) {
                Text(zone.name, color = AeroTwinColors.TextPrimary, fontWeight = FontWeight.Bold)
                Text("Zona activa", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
            }
            Icon(Icons.AutoMirrored.Outlined.ArrowForward, null, tint = AeroTwinColors.Primary)
        }
    }
}

@Composable
private fun InspectionPage(viewModel: AeroTwinViewModel) {
    val inspection = viewModel.uiState.inspection ?: return
    LaunchedEffect(inspection.id) {
        while (true) {
            delay(1_500)
            viewModel.refreshProgress(inspection.id)
        }
    }
    Screen {
        AeroTopBar("Inspección activa", "Zona ${inspection.zoneCode}", "Verificación física en curso.")
        Spacer(Modifier.height(18.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            ConnectionIndicator(connected = viewModel.uiState.coreConnected)
            StatusBadge("En curso", AeroStatusTone.INFO)
        }
        Spacer(Modifier.height(28.dp))
        MetricTile("Posiciones verificadas", "${inspection.completedLocations} / ${inspection.totalLocations}", "Progreso de la zona ${inspection.zoneCode}")
        Spacer(Modifier.height(16.dp))
        InspectionProgress(inspection.completedLocations, inspection.totalLocations)
        Spacer(Modifier.height(30.dp))
        SectionHeader("Modo de captura")
        Spacer(Modifier.height(12.dp))
        StateBanner(
            title = "SENSOR MODE",
            message = "Abre Modo Sensor en cada teléfono. En el prototipo se unen automáticamente a la inspección activa.",
            tone = AeroStatusTone.INFO,
            icon = Icons.AutoMirrored.Outlined.FactCheck,
        )
        Spacer(Modifier.height(24.dp))
        ActionButton("MONITOREAR DRON", viewModel::monitorDrone, icon = Icons.Outlined.Wifi)
        Spacer(Modifier.height(10.dp))
        if (viewModel.uiState.user?.role == "SUPERVISOR") {
            SecondaryAction("REVISAR EXCEPCIONES", viewModel::openReviewExceptions)
            Spacer(Modifier.height(10.dp))
        }
        SecondaryAction("MODO MANUAL", viewModel::startManualReading)
        Spacer(Modifier.height(10.dp))
        TextButton(onClick = viewModel::backToHome) { Text("Volver a inicio", color = AeroTwinColors.TextSecondary) }
    }
}

@Composable
private fun SensorPage(viewModel: AeroTwinViewModel) {
    val context = LocalContext.current
    var hasPermission by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.RequestPermission(),
    ) { granted ->
        hasPermission = granted
        viewModel.onCameraPermissionChanged(granted)
    }
    LaunchedEffect(Unit) { if (!hasPermission) permissionLauncher.launch(Manifest.permission.CAMERA) }
    val sensor = viewModel.sensorUiState
    val inspection = viewModel.uiState.inspection ?: return
    Box(modifier = Modifier.fillMaxSize().background(AeroTwinColors.PrimaryDark)) {
        if (hasPermission) {
            SensorCameraPreview(
                state = sensor,
                onDetections = viewModel::onSensorDetections,
                onImageCaptured = viewModel::onSensorImageCaptured,
                onCaptureFailed = viewModel::onSensorCaptureFailed,
                onLiveFrame = viewModel::uploadLiveFrame,
                onObjects = viewModel::onObjectDetections,
                onAnalyzerStatus = viewModel::onAnalyzerStatus,
                modifier = Modifier.fillMaxSize(),
            )
            SensorBoundingBox(sensor.copy(detections = sensor.detections + viewModel.objectDetections), Modifier.fillMaxSize())
        }
        Column(modifier = Modifier.fillMaxSize().padding(start = 18.dp, end = 18.dp, top = 42.dp, bottom = 24.dp)) {
            // --- Top HUD: sensor identity ---
            Column(modifier = Modifier.fillMaxWidth().background(Color(0xDD18212B), RoundedCornerShape(10.dp)).padding(14.dp)) {
                Text("● SENSOR ACTIVO", color = AeroTwinColors.Success, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                Spacer(Modifier.height(4.dp))
                Text("Zona ${inspection.zoneCode} · ${sensorTitle(sensor.phase)}", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 19.sp)
                viewModel.sensorObjective?.locationCode?.let { target ->
                    Text("Objetivo Core: $target · ${viewModel.sensorObjective?.reason ?: "inspección pendiente"}", color = Color(0xFFB8D5FF), fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                }
                Text(viewModel.analyzerStatus, color = Color(0xFFDCE7F7), fontSize = 13.sp)
                Text(viewModel.liveStatus, color = Color(0xFFDCE7F7), fontSize = 12.sp)
            }
            Spacer(Modifier.weight(1f))
            // --- Bottom HUD: context-sensitive panel ---
            if (!hasPermission) {
                StateBanner("CÁMARA REQUERIDA", sensor.message, AeroStatusTone.WARNING, Icons.Outlined.Wifi)
                Spacer(Modifier.height(12.dp))
                ActionButton("CONCEDER PERMISO", { permissionLauncher.launch(Manifest.permission.CAMERA) })
            } else {
                val result = viewModel.uiState.result?.takeIf { sensor.phase == SensorPhase.RESULT }
                if (result != null) {
                    // --- ENRICHED RESULT PANEL ---
                    SensorResultPanel(result, viewModel)
                } else {
                    // --- SCANNING STATUS PANEL ---
                    SensorScanningPanel(sensor, viewModel)
                }
            }
        }
    }
}

/** Panel shown while the sensor is actively scanning (not showing a result). */
@Composable
private fun SensorScanningPanel(sensor: SensorUiState, viewModel: AeroTwinViewModel) {
    Column(modifier = Modifier.fillMaxWidth().background(Color(0xDD18212B), RoundedCornerShape(10.dp)).padding(14.dp)) {
        Text(sensor.message, color = Color.White, fontWeight = FontWeight.SemiBold)
        sensor.locationCode?.let {
            Spacer(Modifier.height(4.dp))
            Text("Ubicación: $it", color = AeroTwinColors.Success, fontWeight = FontWeight.Bold)
        }
        // Show previous quality during ReScan
        sensor.previousQuality?.let { prev ->
            Spacer(Modifier.height(4.dp))
            Text("Intento anterior: $prev / 100 · Reintentando…", color = Color(0xFFF2B84B), fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
        }
        sensor.quality?.let { quality ->
            Spacer(Modifier.height(4.dp))
            Text("Calidad: ${quality.score} / 100", color = Color.White, fontFamily = FontFamily.Monospace)
        }
        Spacer(Modifier.height(4.dp))
        Text("Captura automática activa · sin botón manual", color = Color(0xFFDCE7F7), fontSize = 12.sp)
        viewModel.uiState.error?.let {
            Spacer(Modifier.height(4.dp))
            Text(it, color = Color(0xFFFFB4AB), fontSize = 13.sp)
        }
    }
}

/** Sensor mode reports operational outcome only; interpretation belongs to Control Station. */
@Composable
private fun SensorResultPanel(result: ReadingDto, viewModel: AeroTwinViewModel) {
    Column(
        modifier = Modifier.fillMaxWidth().background(Color(0xDD18212B), RoundedCornerShape(10.dp)).padding(16.dp),
    ) {
        Text(if (result.readingStatus == "HUMAN_REVIEW_REQUIRED") "LECTURA NO RESUELTA" else "LECTURA COMPLETADA", color = if (result.readingStatus == "HUMAN_REVIEW_REQUIRED") Color(0xFFF2B84B) else AeroTwinColors.Success, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(8.dp))
        Text(result.locationCode, color = Color.White, fontFamily = FontFamily.Monospace, fontSize = 20.sp, fontWeight = FontWeight.Bold)
        result.observedPalletCode?.let { Text(it, color = Color.White, fontFamily = FontFamily.Monospace, fontSize = 16.sp) }
        Spacer(Modifier.height(6.dp))
        Text(if (result.readingStatus == "HUMAN_REVIEW_REQUIRED") "Caso enviado a supervisión" else "✓ Enviado al Core", color = Color(0xFFDCE7F7))
        Text("Continuando según misión…", color = Color(0xFFDCE7F7), fontSize = 12.sp)
    }
}

@Composable
private fun DroneMonitorPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    androidx.activity.compose.BackHandler { viewModel.backToInspectionFromMonitor() }
    Screen {
        AeroTopBar("Control Station · 0.2.0", "Monitorear drones", "Vistas actuales · actualización automática. Las fotos de evidencia se registran al validar los QR.")
        Spacer(Modifier.height(20.dp))
        if (state.drones.isEmpty()) {
            StateBanner("Buscando drones", "Abre Modo Sensor en un teléfono conectado al mismo servidor.", AeroStatusTone.INFO, Icons.Outlined.Wifi)
        }
        if (state.drones.isNotEmpty()) {
            Text("Sensores conectados", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
            Spacer(Modifier.height(8.dp))
            state.drones.forEach { drone ->
                val selected = drone.id == state.selectedDroneId
                TextButton(onClick = { viewModel.selectDrone(drone.id) }) {
                    Text("${if (selected) "● " else "○ "}${drone.deviceCode} · ${drone.name}", color = if (selected) AeroTwinColors.Primary else AeroTwinColors.TextSecondary)
                }
            }
            Spacer(Modifier.height(12.dp))
            val drone = state.drones.firstOrNull { it.id == state.selectedDroneId } ?: state.drones.first()
            val frame = state.liveFrames[drone.id]
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                OperationalCode(drone.deviceCode, drone.name.uppercase())
                StatusBadge(if (frame != null) "En vivo" else "Sin señal", if (frame != null) AeroStatusTone.SUCCESS else AeroStatusTone.NEUTRAL)
            }
            Spacer(Modifier.height(18.dp))
            if (frame != null) {
                Image(bitmap = frame.asImageBitmap(), contentDescription = "Vista actual de ${drone.deviceCode}", contentScale = ContentScale.Fit, modifier = Modifier.fillMaxWidth().height(360.dp).background(AeroTwinColors.PrimaryDark, RoundedCornerShape(8.dp)))
                Spacer(Modifier.height(12.dp))
            } else StateBanner("Sin transmisión reciente", "Mantén la cámara del sensor abierta. No es necesario escanear un QR para ver su imagen.", AeroStatusTone.INFO, Icons.Outlined.Wifi)
            drone.liveMessage?.let { message ->
                Spacer(Modifier.height(10.dp))
                StateBanner(message, drone.lastDetectedCode?.let { "Código: $it" } ?: "El Sensor está analizando el entorno.", AeroStatusTone.SUCCESS, Icons.AutoMirrored.Outlined.FactCheck)
            }
            drone.lastReading?.let { Text("Evidencia registrada: ${it.locationCode} · ${it.observedPalletCode ?: "VACÍO"} · ${it.comparisonResult}", color = AeroTwinColors.TextPrimary, fontWeight = FontWeight.SemiBold) }
            Spacer(Modifier.height(22.dp))
        }
        ErrorMessage(state.error)
        TextButton(onClick = viewModel::backToInspectionFromMonitor) { Text("Volver a inspección", color = AeroTwinColors.TextSecondary) }
    }
}

@Composable
private fun SupervisorExceptionsPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    androidx.activity.compose.BackHandler { viewModel.backToInspectionFromExceptions() }
    Screen {
        AeroTopBar("Control Station", "Excepciones pendientes", "Cada intento conserva su evidencia para revisión.")
        Spacer(Modifier.height(18.dp))
        if (state.loading) Text("Cargando excepciones…", color = AeroTwinColors.TextSecondary)
        if (!state.loading && state.reviewExceptions.isEmpty()) {
            StateBanner("SIN EXCEPCIONES", "No hay lecturas que requieran revisión humana.", AeroStatusTone.SUCCESS, Icons.AutoMirrored.Outlined.FactCheck)
        }
        state.reviewExceptions.forEach { exception ->
            Column(modifier = Modifier.fillMaxWidth().background(AeroTwinColors.Surface, RoundedCornerShape(10.dp)).padding(16.dp)) {
                Text("HUMAN REVIEW REQUIRED", color = AeroTwinColors.Warning, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                Text(exception.locationCode, color = AeroTwinColors.TextPrimary, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                Text("Esperado: ${exception.expectedPalletCode ?: "sin pallet esperado"}", color = AeroTwinColors.TextSecondary)
                Spacer(Modifier.height(8.dp))
                Text("Secuencia de evidencia · ${exception.evidenceAttempts.size} intento(s)", color = AeroTwinColors.TextPrimary, fontWeight = FontWeight.SemiBold)
                exception.evidenceAttempts.forEach { evidence ->
                    Text("Intento ${evidence.attemptNumber} · evidencia #${evidence.evidenceId}", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
                    state.reviewEvidence[evidence.evidenceId]?.let { frame ->
                        Image(
                            bitmap = frame.asImageBitmap(),
                            contentDescription = "Evidencia del intento ${evidence.attemptNumber}",
                            contentScale = ContentScale.Fit,
                            modifier = Modifier.fillMaxWidth().height(140.dp).background(AeroTwinColors.PrimaryDark, RoundedCornerShape(6.dp)),
                        )
                    }
                }
                Spacer(Modifier.height(14.dp))
                ActionButton("CONFIRMAR VACÍO", { viewModel.confirmExceptionEmpty(exception.readingGroupId) })
            }
            Spacer(Modifier.height(14.dp))
        }
        ErrorMessage(state.error)
        TextButton(onClick = viewModel::backToInspectionFromExceptions) { Text("Volver a inspección", color = AeroTwinColors.TextSecondary) }
    }
}

private fun sensorTitle(phase: SensorPhase): String = when (phase) {
    SensorPhase.SEARCHING_LOCATION -> "Buscando ubicación"
    SensorPhase.VALIDATING_LOCATION -> "Validando ubicación"
    SensorPhase.SEARCHING_PALLET -> "Buscando pallet"
    SensorPhase.CAPTURING -> "Capturando evidencia"
    SensorPhase.PROCESSING -> "Procesando lectura"
    SensorPhase.RESULT -> "Resultado de inspección"
    SensorPhase.CAMERA_PERMISSION_REQUIRED -> "Permiso de cámara"
}

private fun comparisonLabel(result: String): String = when (result) {
    "CORRECT", "CORRECT_EMPTY" -> "CORRECTO"
    "PALLET_MISMATCH" -> "DIFERENCIA DE PALLET"
    "UNEXPECTED_PALLET" -> "PALLET NO ESPERADO"
    "EXPECTED_PALLET_MISSING" -> "FALTA PALLET ESPERADO"
    "UNRESOLVED" -> "SIN RESOLVER"
    else -> result
}


private fun resultSeverityTone(severity: String): AeroStatusTone = when (severity) {
    "CRITICAL", "HIGH" -> AeroStatusTone.CRITICAL
    "MEDIUM" -> AeroStatusTone.WARNING
    "LOW", "INFO" -> AeroStatusTone.INFO
    else -> AeroStatusTone.NEUTRAL
}

@Composable
private fun ReadingPage(viewModel: AeroTwinViewModel) {
    val state = viewModel.uiState
    val inspection = state.inspection ?: return
    Screen {
        AeroTopBar(
            "Captura manual · Zona ${inspection.zoneCode}",
            if (state.result?.readingStatus == "RESCAN_REQUIRED") "ReScan requerido" else "Verificar posición",
            "${inspection.completedLocations} de ${inspection.totalLocations} posiciones verificadas",
        )
        Spacer(Modifier.height(18.dp))
        StatusBadge("Modo manual demo", AeroStatusTone.INFO)
        Spacer(Modifier.height(24.dp))
        state.result?.let { result ->
            ResultExperience(result)
            Spacer(Modifier.height(24.dp))
            if (result.isFinal) {
                ActionButton("SIGUIENTE POSICIÓN", viewModel::nextReading, icon = Icons.AutoMirrored.Outlined.ArrowForward)
                Spacer(Modifier.height(10.dp))
                SecondaryAction("VOLVER A INSPECCIÓN", viewModel::backToInspection)
                return@Screen
            }
        }
        ReadingForm(viewModel, state.loading)
        ErrorMessage(state.error)
    }
}

@Composable
private fun ReadingForm(viewModel: AeroTwinViewModel, loading: Boolean) {
    val rescan = viewModel.uiState.result?.readingStatus == "RESCAN_REQUIRED"
    if (rescan) {
        StateBanner("REINTENTAR LECTURA", "Ajusta la captura y vuelve a verificar esta misma posición.", AeroStatusTone.WARNING, Icons.Outlined.Refresh)
        Spacer(Modifier.height(22.dp))
    }
    SectionHeader("01 · Ubicación")
    Spacer(Modifier.height(10.dp))
    OutlinedTextField(
        value = viewModel.locationCode,
        onValueChange = viewModel::onLocationChanged,
        modifier = Modifier.fillMaxWidth(),
        label = { Text("Código de ubicación") },
        placeholder = { Text("A-01-01") },
        textStyle = TextStyle(fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 19.sp),
        singleLine = true,
        shape = RoundedCornerShape(8.dp),
    )
    Spacer(Modifier.height(24.dp))
    AeroDivider()
    Spacer(Modifier.height(24.dp))
    SectionHeader("02 · Observación")
    Spacer(Modifier.height(10.dp))
    ObservationSelector(viewModel)
    if (viewModel.observedState == "PALLET") {
        Spacer(Modifier.height(14.dp))
        OutlinedTextField(
            value = viewModel.palletCode,
            onValueChange = viewModel::onPalletChanged,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Pallet detectado") },
            placeholder = { Text("PAL-001") },
            textStyle = TextStyle(fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 19.sp),
            singleLine = true,
            shape = RoundedCornerShape(8.dp),
        )
    }
    Spacer(Modifier.height(24.dp))
    AeroDivider()
    Spacer(Modifier.height(24.dp))
    SectionHeader("03 · Calidad")
    Spacer(Modifier.height(10.dp))
    Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = viewModel.qualityScore,
            onValueChange = viewModel::onQualityChanged,
            modifier = Modifier.width(136.dp),
            label = { Text("Score") },
            textStyle = TextStyle(fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, fontSize = 24.sp),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            singleLine = true,
            shape = RoundedCornerShape(8.dp),
        )
        Spacer(Modifier.width(16.dp))
        Column {
            Text("Umbral de aceptación", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
            Text("85 / 100", color = AeroTwinColors.TextPrimary, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
        }
    }
    Spacer(Modifier.height(24.dp))
    AeroDivider()
    Spacer(Modifier.height(24.dp))
    EvidencePicker(viewModel, loading)
    Spacer(Modifier.height(28.dp))
    ActionButton(
        text = if (loading) "PROCESANDO LECTURA…" else if (rescan) "ENVIAR REESCANEO" else "VERIFICAR POSICIÓN",
        enabled = !loading,
        onClick = viewModel::submitReading,
        icon = Icons.AutoMirrored.Outlined.FactCheck,
    )
}

@Composable
private fun EvidencePicker(viewModel: AeroTwinViewModel, loading: Boolean) {
    val launcher = rememberLauncherForActivityResult(PickVisualMedia()) { uri ->
        viewModel.selectEvidence(uri)
    }
    SectionHeader("04 · Evidencia")
    Spacer(Modifier.height(10.dp))
    val prepared = viewModel.evidence
    if (prepared == null) {
        StateBanner(
            title = "EVIDENCIA REQUERIDA",
            message = "Adjunta una fotografía. Se aceptan JPEG, PNG y WebP; la app la normaliza antes de enviarla.",
            tone = AeroStatusTone.INFO,
            icon = Icons.AutoMirrored.Outlined.FactCheck,
        )
    } else {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Image(
                bitmap = prepared.preview.asImageBitmap(),
                contentDescription = "Vista previa de evidencia",
                contentScale = ContentScale.Crop,
                modifier = Modifier.width(86.dp).height(64.dp).border(1.dp, AeroTwinColors.Border, RoundedCornerShape(6.dp)),
            )
            Spacer(Modifier.width(14.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text("Imagen seleccionada ✓", color = AeroTwinColors.Success, fontWeight = FontWeight.Bold)
                Text("JPEG preparado · ${prepared.jpegBytes.size / 1024} KB", color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
            }
            TextButton(onClick = viewModel::clearEvidence, enabled = !loading) {
                Text("Cambiar", color = AeroTwinColors.Primary)
            }
        }
    }
    Spacer(Modifier.height(12.dp))
    SecondaryAction(
        text = if (prepared == null) "SELECCIONAR IMAGEN" else "REEMPLAZAR IMAGEN",
        enabled = !loading,
        onClick = { launcher.launch(PickVisualMediaRequest(PickVisualMedia.ImageOnly)) },
    )
}

@Composable
private fun ObservationSelector(viewModel: AeroTwinViewModel) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        listOf("PALLET", "EMPTY", "UNRESOLVED").forEach { option ->
            val selected = viewModel.observedState == option
            OutlinedButton(
                onClick = { viewModel.onObservedStateChanged(option) },
                modifier = Modifier.weight(1f).height(46.dp),
                shape = RoundedCornerShape(8.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, if (selected) AeroTwinColors.Primary else AeroTwinColors.Border),
                colors = androidx.compose.material3.ButtonDefaults.outlinedButtonColors(
                    containerColor = if (selected) AeroTwinColors.InfoSoft else Color.Transparent,
                    contentColor = if (selected) AeroTwinColors.Primary else AeroTwinColors.TextSecondary,
                ),
                contentPadding = androidx.compose.material3.ButtonDefaults.TextButtonContentPadding,
            ) { Text(observedStateLabel(option), fontSize = 10.sp, fontWeight = FontWeight.Bold) }
        }
    }
}

@Composable
private fun ResultExperience(result: ReadingDto) {
    when {
        result.readingStatus == "RESCAN_REQUIRED" -> RescanResult(result)
        result.readingStatus == "HUMAN_REVIEW_REQUIRED" -> HumanReviewResult(result)
        result.comparisonResult == "CORRECT" || result.comparisonResult == "CORRECT_EMPTY" -> CorrectResult(result)
        else -> MismatchResult(result)
    }
}

@Composable
private fun CorrectResult(result: ReadingDto) {
    StateBanner("VERIFICACIÓN CORRECTA", "La posición coincide con el inventario esperado.", AeroStatusTone.SUCCESS, Icons.Outlined.CheckCircle)
    Spacer(Modifier.height(24.dp))
    OperationalCode("Ubicación", result.locationCode, AeroTwinColors.Success)
    Spacer(Modifier.height(22.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
        Box(Modifier.weight(1f)) { MetricTile("Esperado", result.expectedPalletCode ?: "VACÍO") }
        Box(Modifier.weight(1f)) { MetricTile("Observado", result.observedPalletCode ?: result.observedState) }
    }
    Spacer(Modifier.height(12.dp))
    MetricTile("Calidad de lectura", "${result.qualityScore} / 100", "Resultado aceptado")
    EvidenceSaved(result)
}

@Composable
private fun MismatchResult(result: ReadingDto) {
    StateBanner("DISCREPANCIA DETECTADA", "El pallet observado no coincide con el inventario esperado.", AeroStatusTone.CRITICAL, Icons.Outlined.ErrorOutline)
    Spacer(Modifier.height(24.dp))
    OperationalCode("Ubicación", result.locationCode, AeroTwinColors.Critical)
    Spacer(Modifier.height(22.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
        Box(Modifier.weight(1f)) { MetricTile("Esperado", result.expectedPalletCode ?: "VACÍO") }
        Box(Modifier.weight(1f)) { MetricTile("Observado", result.observedPalletCode ?: result.observedState) }
    }
    Spacer(Modifier.height(16.dp))
    MetricTile("Nivel de riesgo", result.riskScore.toString(), severityLabel(result.severity))
    result.riskBreakdown.entries.firstOrNull()?.let { (rule, points) ->
        Spacer(Modifier.height(12.dp))
        Text("${riskLabel(rule)}  +$points", color = AeroTwinColors.Critical, fontWeight = FontWeight.SemiBold)
    }
    EvidenceSaved(result)
}

@Composable
private fun RescanResult(result: ReadingDto) {
    StateBanner("LECTURA INSUFICIENTE", "La captura no cumple el umbral requerido de 85.", AeroStatusTone.WARNING, Icons.Outlined.WarningAmber)
    Spacer(Modifier.height(24.dp))
    OperationalCode("Calidad obtenida", "${result.qualityScore} / 100", AeroTwinColors.Warning)
    Spacer(Modifier.height(20.dp))
    AeroDivider()
    Spacer(Modifier.height(16.dp))
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        OperationalCode("Intento", "${result.attemptNumber} / 2")
        StatusBadge("ReScan requerido", AeroStatusTone.WARNING)
    }
    EvidenceSaved(result)
}

@Composable
private fun HumanReviewResult(result: ReadingDto) {
    StateBanner(
        "REVISIÓN REQUERIDA",
        "No se obtuvo una lectura suficientemente confiable después de 2 intentos. La posición queda pendiente de validación humana.",
        AeroStatusTone.WARNING,
        Icons.Outlined.WarningAmber,
    )
    Spacer(Modifier.height(24.dp))
    OperationalCode("Ubicación", result.locationCode, AeroTwinColors.Warning)
    Spacer(Modifier.height(20.dp))
    MetricTile("Calidad final", "${result.qualityScore} / 100", "Intento ${result.attemptNumber} de 2")
    EvidenceSaved(result)
}

@Composable
private fun EvidenceSaved(result: ReadingDto) {
    Spacer(Modifier.height(16.dp))
    Text(
        "Evidencia guardada ✓  ·  ${evidenceTypeLabel(result.evidence.evidenceType)}",
        color = AeroTwinColors.Success,
        fontSize = 13.sp,
        fontWeight = FontWeight.SemiBold,
    )
}

@Composable
private fun ErrorMessage(error: String?) {
    error?.let {
        Spacer(Modifier.height(16.dp))
        StateBanner("No se pudo completar la acción", it, AeroStatusTone.CRITICAL, Icons.Outlined.ErrorOutline)
    }
}

@Composable
private fun LoadingState(message: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        CircularProgressIndicator(modifier = Modifier.height(20.dp), color = AeroTwinColors.Primary, strokeWidth = 2.dp)
        Spacer(Modifier.width(10.dp))
        Text(message, color = AeroTwinColors.TextSecondary)
    }
}

private fun resultTone(reading: ReadingDto): AeroStatusTone = when {
    reading.readingStatus == "RESCAN_REQUIRED" || reading.readingStatus == "HUMAN_REVIEW_REQUIRED" -> AeroStatusTone.WARNING
    reading.comparisonResult == "CORRECT" || reading.comparisonResult == "CORRECT_EMPTY" -> AeroStatusTone.SUCCESS
    else -> AeroStatusTone.CRITICAL
}

private fun readingStatusLabel(reading: ReadingDto): String = when {
    reading.readingStatus == "RESCAN_REQUIRED" -> "Reescaneo"
    reading.readingStatus == "HUMAN_REVIEW_REQUIRED" -> "Revisión"
    reading.comparisonResult == "CORRECT" || reading.comparisonResult == "CORRECT_EMPTY" -> "Correcta"
    else -> "Discrepancia"
}

private fun riskLabel(rule: String): String = when (rule) {
    "PALLET_MISMATCH" -> "Pallet diferente al esperado"
    "EXPECTED_PALLET_MISSING" -> "Pallet esperado no encontrado"
    "UNEXPECTED_PALLET" -> "Pallet inesperado"
    "LOW_QUALITY" -> "Lectura de baja calidad"
    else -> rule.replace('_', ' ')
}

private fun observedStateLabel(value: String): String = when (value) {
    "PALLET" -> "Pallet"
    "EMPTY" -> "Vacío"
    "UNRESOLVED" -> "Sin resolver"
    else -> value
}

private fun evidenceTypeLabel(value: String): String = when (value) {
    "ORIGINAL" -> "Evidencia original"
    "RESCAN" -> "Evidencia de reescaneo"
    "EMPTY_CONFIRMATION" -> "Confirmación de vacío"
    "MANUAL_REVIEW" -> "Revisión manual"
    else -> "Evidencia"
}

private fun qualityReasonLabel(value: String): String = when (value) {
    "STABLE_READING" -> "Lectura estable"
    "LOW_BRIGHTNESS" -> "Iluminación baja"
    "TOO_FAR" -> "Código demasiado lejano"
    "UNSTABLE_READING" -> "Código inestable"
    else -> "Calidad por revisar"
}

private fun severityLabel(value: String): String = when (value) {
    "INFO" -> "Informativo"
    "LOW" -> "Bajo"
    "MEDIUM" -> "Medio"
    "HIGH" -> "Alto"
    "CRITICAL" -> "Crítico"
    else -> value
}
