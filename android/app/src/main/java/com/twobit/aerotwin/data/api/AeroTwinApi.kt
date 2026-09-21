package com.twobit.aerotwin.data.api

import com.google.gson.Gson
import com.google.gson.annotations.SerializedName
import java.util.concurrent.TimeUnit
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.Response
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.Multipart
import retrofit2.http.Part
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming

data class LoginRequest(val username: String, val password: String)

data class UserDto(
    val id: Int,
    val username: String,
    @SerializedName("full_name") val fullName: String,
    val role: String,
)

data class LoginResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("token_type") val tokenType: String,
    val user: UserDto,
)

data class ZoneDto(
    val id: Int,
    val code: String,
    val name: String,
    @SerializedName("is_active") val isActive: Boolean,
)

data class LocationDto(
    val id: Int,
    val code: String,
    @SerializedName("zone_id") val zoneId: Int,
    @SerializedName("zone_code") val zoneCode: String,
    @SerializedName("is_active") val isActive: Boolean,
)

data class InspectionCreateRequest(@SerializedName("zone_id") val zoneId: Int)

data class InspectionDto(
    val id: Int,
    @SerializedName("zone_id") val zoneId: Int,
    @SerializedName("zone_code") val zoneCode: String,
    val status: String,
    @SerializedName("started_at") val startedAt: String,
    @SerializedName("total_locations") val totalLocations: Int,
    @SerializedName("completed_locations") val completedLocations: Int,
)

data class ReadingCreateRequest(
    @SerializedName("client_reading_id") val clientReadingId: String,
    @SerializedName("location_id") val locationId: Int,
    @SerializedName("reading_group_id") val readingGroupId: String,
    @SerializedName("attempt_number") val attemptNumber: Int,
    @SerializedName("observed_pallet_code") val observedPalletCode: String?,
    @SerializedName("observed_state") val observedState: String,
    @SerializedName("quality_score") val qualityScore: Int,
    @SerializedName("source_type") val sourceType: String = "MANUAL_DEMO",
    @SerializedName("empty_confirmed_by_operator") val emptyConfirmedByOperator: Boolean,
)

data class ReadingDto(
    val id: Int,
    @SerializedName("inspection_id") val inspectionId: Int,
    @SerializedName("location_code") val locationCode: String,
    @SerializedName("attempt_number") val attemptNumber: Int,
    @SerializedName("expected_pallet_code") val expectedPalletCode: String?,
    @SerializedName("observed_pallet_code") val observedPalletCode: String?,
    @SerializedName("observed_state") val observedState: String,
    @SerializedName("quality_score") val qualityScore: Int,
    @SerializedName("reading_status") val readingStatus: String,
    @SerializedName("comparison_result") val comparisonResult: String,
    @SerializedName("is_final") val isFinal: Boolean,
    @SerializedName("risk_score") val riskScore: Int,
    val severity: String,
    @SerializedName("risk_breakdown") val riskBreakdown: Map<String, Int>,
    val evidence: EvidenceDto,
)

data class EvidenceDto(
    val id: Int,
    @SerializedName("mime_type") val mimeType: String,
    @SerializedName("evidence_type") val evidenceType: String,
)

data class SensorRegisterRequest(val name: String)
data class SensorRegisterDto(
    val id: Int,
    @SerializedName("device_code") val deviceCode: String,
    val name: String,
    @SerializedName("device_token") val deviceToken: String,
)
data class SensorMissionDto(
    @SerializedName("inspection_id") val inspectionId: Int,
    val zone: String,
    val status: String,
)
/**
 * Core owns the inspection queue.  A sensor only receives this directive and
 * never attempts to score or select a location locally.
 */
data class SensorNextObjectiveDto(
    val action: String,
    val reason: String,
    @SerializedName("location_id") val locationId: Int? = null,
    @SerializedName("location_code") val locationCode: String? = null,
    val priority: Int? = null,
)
data class SensorTelemetryRequest(
    val message: String,
    @SerializedName("detected_code") val detectedCode: String?,
)
data class EvidenceAttemptDto(
    val id: Int,
    @SerializedName("attempt_number") val attemptNumber: Int,
    @SerializedName("evidence_id") val evidenceId: Int,
    @SerializedName("captured_at") val capturedAt: String,
)
data class ReviewExceptionDto(
    @SerializedName("reading_group_id") val readingGroupId: String,
    @SerializedName("location_code") val locationCode: String,
    @SerializedName("expected_pallet_code") val expectedPalletCode: String?,
    val status: String,
    val attempts: Int,
    @SerializedName("evidence_attempts") val evidenceAttempts: List<EvidenceAttemptDto>,
)
data class EmptyConfirmationRequest(@SerializedName("reading_group_id") val readingGroupId: String)
data class SensorLocationDto(val id: Int, val code: String)
data class SensorLastReadingDto(
    @SerializedName("evidence_id") val evidenceId: Int,
    @SerializedName("location_code") val locationCode: String,
    @SerializedName("observed_pallet_code") val observedPalletCode: String?,
    @SerializedName("comparison_result") val comparisonResult: String,
    @SerializedName("created_at") val createdAt: String,
)
data class SensorStatusDto(
    val id: Int,
    @SerializedName("device_code") val deviceCode: String,
    val name: String,
    val status: String,
    val mission: SensorMissionDto?,
    @SerializedName("last_reading") val lastReading: SensorLastReadingDto?,
    @SerializedName("live_message") val liveMessage: String?,
    @SerializedName("last_detected_code") val lastDetectedCode: String?,
)

data class ErrorBody(val error: ApiErrorDto?)
data class ApiErrorDto(val code: String?, val message: String?)
data class DashboardInspectionDto(val active: Boolean, @SerializedName("inspection_id") val inspectionId: Int?, @SerializedName("zone_code") val zoneCode: String?, val verified: Int, val total: Int, @SerializedName("coverage_percent") val coveragePercent: Double)
data class DashboardExceptionsDto(val open: Int, val critical: Int, val high: Int, @SerializedName("human_review") val humanReview: Int)
data class DashboardRisksDto(@SerializedName("expiring_soon") val expiringSoon: Int, @SerializedName("low_coverage") val lowCoverage: Int, val fefo: Int)
data class ExceptionSummaryDto(val id: Int, val location: String, val type: String, val severity: String, val status: String, @SerializedName("risk_score") val riskScore: Int, @SerializedName("short_reason") val shortReason: String)
data class DashboardSensorDto(val id: Int, val name: String, val code: String, val status: String)
data class DashboardDto(val inspection: DashboardInspectionDto, val exceptions: DashboardExceptionsDto, @SerializedName("inventory_risks") val inventoryRisks: DashboardRisksDto, val priorities: List<ExceptionSummaryDto>, val sensors: List<DashboardSensorDto>)
data class ExceptionsDto(val items: List<ExceptionSummaryDto>, val total: Int)
/**
 * Deliberately small live projection used by the operator surfaces.  It is not
 * a second analytics dashboard: Core owns the physical state and this DTO only
 * renders the active inspection while the phone is looking at it.
 */
data class LiveInspectionStateDto(
    @SerializedName("inspection_id") val inspectionId: Int,
    val zone: String? = null,
    val total: Int = 0,
    val inspected: Int = 0,
    val validated: Int = 0,
    @SerializedName("review_required") val reviewRequired: Int = 0,
    val pending: Int = 0,
    @SerializedName("coverage_percent") val coveragePercent: Double = 0.0,
    @SerializedName("last_final_reading") val lastFinalReading: LiveFinalReadingDto? = null,
    @SerializedName("current_target") val currentTarget: LiveInspectionTargetDto? = null,
    val locations: List<LiveLocationDto> = emptyList(),
)

data class LiveFinalReadingDto(
    @SerializedName("location_id") val locationId: Int? = null,
    @SerializedName("location_code") val locationCode: String? = null,
    @SerializedName("observed_pallet_code") val observedPalletCode: String? = null,
    @SerializedName("comparison_result") val comparisonResult: String? = null,
    @SerializedName("reading_status") val readingStatus: String? = null,
    @SerializedName("risk_score") val riskScore: Int? = null,
    val severity: String? = null,
)

data class LiveInspectionTargetDto(
    val action: String? = null,
    @SerializedName("location_id") val locationId: Int? = null,
    @SerializedName("location_code") val locationCode: String? = null,
    val reason: String? = null,
    val priority: Int? = null,
)

data class LiveLocationDto(
    val id: Int? = null,
    val code: String,
    @SerializedName("row_index") val rowIndex: Int? = null,
    @SerializedName("column_index") val columnIndex: Int? = null,
    val level: Int? = null,
    @SerializedName("physical_state") val physicalState: String? = null,
    @SerializedName("expected_pallet_code") val expectedPalletCode: String? = null,
    @SerializedName("observed_pallet_code") val observedPalletCode: String? = null,
    val product: String? = null,
    val sku: String? = null,
    @SerializedName("expected_quantity") val expectedQuantity: Int? = null,
    @SerializedName("observed_quantity") val observedQuantity: Int? = null,
    @SerializedName("comparison_result") val comparisonResult: String? = null,
    val result: String? = null,
    @SerializedName("risk_score") val riskScore: Int? = null,
    val severity: String? = null,
    val badges: List<String> = emptyList(),
    val lot: String? = null,
    @SerializedName("days_to_expiry") val daysToExpiry: Int? = null,
    val rotation: String? = null,
    @SerializedName("coverage_days") val coverageDays: Double? = null,
    @SerializedName("fefo_risk") val fefoRisk: Boolean? = null,
    @SerializedName("loss_prevention_signal") val lossPreventionSignal: String? = null,
    @SerializedName("loss_prevention_reason") val lossPreventionReason: String? = null,
    @SerializedName("slotting_suggestion") val slottingSuggestion: String? = null,
    @SerializedName("exception_id") val exceptionId: Int? = null,
    @SerializedName("evidence_id") val evidenceId: Int? = null,
)
data class FlowTwinSummaryDto(val compared: Int, val unchanged: Int, val changed: Int, val persistent: Int, val unresolved: Int)
data class FlowTwinChangeDto(val location: String, val type: String, val previous: String, val current: String, @SerializedName("risk_score") val riskScore: Int, @SerializedName("exception_id") val exceptionId: Int?)
data class FlowTwinDto(val status: String, @SerializedName("current_inspection_id") val currentInspectionId: Int, @SerializedName("previous_inspection_id") val previousInspectionId: Int?, val summary: FlowTwinSummaryDto, val changes: List<FlowTwinChangeDto>)
data class AgentRequest(val question: String)
data class AgentActionDto(val type: String, val id: Int? = null)
data class AgentResponseDto(val mode: String, val intent: String, val tool: String?, val answer: String, val data: com.google.gson.JsonElement, val sources: List<com.google.gson.JsonElement>, val actions: List<AgentActionDto>)
data class ExceptionEvidenceDto(val id: Int, val type: String, @SerializedName("captured_at") val capturedAt: String)
data class ExceptionDetailDto(val id: Int, val location: String?, val type: String, val severity: String, val status: String, @SerializedName("risk_score") val riskScore: Int, @SerializedName("risk_breakdown") val riskBreakdown: Map<String, Int>, @SerializedName("short_reason") val shortReason: String, val description: String, @SerializedName("expected_pallet") val expectedPallet: String?, @SerializedName("observed_pallet") val observedPallet: String?, val product: String?, val sku: String?, val pallet: String?, val lot: String?, val quantity: Int?, @SerializedName("expiration_date") val expirationDate: String?, @SerializedName("days_to_expiry") val daysToExpiry: Int?, @SerializedName("quality_score") val qualityScore: Int?, @SerializedName("attempt_number") val attemptNumber: Int?, val rotation: String?, @SerializedName("rotation_30d") val rotation30d: Int?, @SerializedName("coverage_days") val coverageDays: Double?, @SerializedName("coverage_status") val coverageStatus: String?, @SerializedName("fefo_risk") val fefoRisk: Boolean, @SerializedName("fefo_reason") val fefoReason: String?, val evidence: List<ExceptionEvidenceDto>)

interface AeroTwinApi {
    @GET("api/v1/memory/locations/{id}")
    suspend fun locationMemory(@Path("id") id: Int): com.google.gson.JsonObject
    @GET("api/v1/memory/locations")
    suspend fun memoryLocations(): com.google.gson.JsonObject
    @POST("api/v1/agent/query")
    suspend fun agentQuery(@Body payload: AgentRequest): AgentResponseDto
    @GET("api/v1/flowtwin/changes")
    suspend fun flowTwinChanges(): FlowTwinDto
    @GET("api/v1/dashboard")
    suspend fun dashboard(): DashboardDto
    @GET("api/v1/exceptions")
    suspend fun exceptions(
        @Query("type") type: String? = null,
        @Query("severity") severity: String? = null,
        @Query("zone") zone: String? = null,
        @Query("expiry") expiry: Boolean? = null,
        @Query("lot") lot: String? = null,
        @Query("quality_max") qualityMax: Int? = null,
    ): ExceptionsDto
    @GET("api/v1/exceptions/{id}")
    suspend fun exceptionDetail(@Path("id") id: Int): ExceptionDetailDto
    @GET("api/v1/health")
    suspend fun health(): HealthResponse

    @POST("api/v1/auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @GET("api/v1/auth/me")
    suspend fun me(): UserDto

    @GET("api/v1/zones")
    suspend fun zones(): List<ZoneDto>

    @GET("api/v1/inspections/active")
    suspend fun activeInspection(): InspectionDto?

    @POST("api/v1/inspections")
    suspend fun createInspection(@Body request: InspectionCreateRequest): InspectionDto

    @GET("api/v1/inspections/{id}")
    suspend fun inspection(@Path("id") id: Int): InspectionDto

    @GET("api/v1/inspections/{id}/live-state")
    suspend fun inspectionLiveState(@Path("id") id: Int): LiveInspectionStateDto

    @GET("api/v1/inspections/{id}/review-exceptions")
    suspend fun reviewExceptions(@Path("id") id: Int): List<ReviewExceptionDto>

    @POST("api/v1/inspections/{id}/review-exceptions/confirm-empty")
    suspend fun confirmExceptionEmpty(@Path("id") id: Int, @Body request: EmptyConfirmationRequest): ReadingDto

    @GET("api/v1/locations/code/{code}")
    suspend fun location(@Path("code") code: String): LocationDto

    @Multipart
    @POST("api/v1/inspections/{id}/readings")
    suspend fun submitReading(
        @Path("id") inspectionId: Int,
        @Part("payload") payload: okhttp3.RequestBody,
        @Part evidence: okhttp3.MultipartBody.Part,
    ): ReadingDto

    @POST("api/v1/sensor/register")
    suspend fun registerSensor(@Body request: SensorRegisterRequest): SensorRegisterDto

    @GET("api/v1/sensor/mission")
    suspend fun sensorMission(): Response<SensorMissionDto?>

    @GET("api/v1/sensor/locations/code/{code}")
    suspend fun sensorLocation(@Path("code") code: String): SensorLocationDto

    @GET("api/v1/sensor/mission/next")
    suspend fun sensorNextObjective(): SensorNextObjectiveDto

    @GET("api/v1/sensor/mission/progress")
    suspend fun sensorMissionProgress(): InspectionDto

    @Multipart
    @POST("api/v1/sensor/mission/readings")
    suspend fun submitSensorReading(
        @Part("payload") payload: okhttp3.RequestBody,
        @Part evidence: okhttp3.MultipartBody.Part,
    ): ReadingDto

    @GET("api/v1/sensors")
    suspend fun sensors(): List<SensorStatusDto>

    @Multipart
    @POST("api/v1/sensor/preview")
    suspend fun uploadPreview(@Part frame: okhttp3.MultipartBody.Part): Response<Unit>

    @POST("api/v1/sensor/telemetry")
    suspend fun uploadTelemetry(@Body payload: SensorTelemetryRequest): Response<Unit>

    @GET("api/v1/sensors/{id}/preview")
    suspend fun livePreview(@Path("id") sensorId: Int): Response<okhttp3.ResponseBody>

    @GET("api/v1/sensors/{id}/status")
    suspend fun sensorStatus(@Path("id") sensorId: Int): SensorStatusDto

    @Streaming
    @GET("api/v1/evidence/{id}")
    suspend fun evidence(@Path("id") evidenceId: Int): okhttp3.ResponseBody
}

object AeroTwinApiFactory {
    private const val TIMEOUT_SECONDS = 8L
    val gson = Gson()
    private val sharedClient = OkHttpClient.Builder()
        .connectTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .writeTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS).build()

    fun create(baseUrl: String, token: String? = null): AeroTwinApi {
        return createWithHeaders(baseUrl, token?.let { "Authorization" to "Bearer $it" })
    }

    fun createSensor(baseUrl: String, deviceToken: String): AeroTwinApi {
        return createWithHeaders(baseUrl, "X-Sensor-Token" to deviceToken)
    }

    private fun createWithHeaders(baseUrl: String, header: Pair<String, String>? = null): AeroTwinApi {
        val client = sharedClient.newBuilder()
            .connectTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .readTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .writeTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .apply {
                if (header != null) {
                    addInterceptor { chain ->
                        val request = chain.request().newBuilder()
                            .header(header.first, header.second)
                            .build()
                        chain.proceed(request)
                    }
                }
            }
            .build()

        return Retrofit.Builder()
            .baseUrl(HealthApiFactory.normalizeBaseUrl(baseUrl))
            .client(client)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
            .create(AeroTwinApi::class.java)
    }
}
