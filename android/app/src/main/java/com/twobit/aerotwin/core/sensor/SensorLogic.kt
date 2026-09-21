package com.twobit.aerotwin.core.sensor

import kotlin.math.abs
import kotlin.math.min

// A decoded QR is already cryptographically structured. One clear temporal frame
// is enough to trigger an automatic still capture, so a moving phone is not blocked.
const val STABLE_FRAMES_REQUIRED = 1

// Si el código desaparece hasta 2 frames consecutivos (oclusión, autofoco),
// el progreso de estabilidad se conserva. Al tercer frame perdido se reinicia.
const val GRACE_FRAMES = 8

sealed interface SensorQrCode {
    val code: String
    data class Location(override val code: String) : SensorQrCode
    data class Pallet(override val code: String) : SensorQrCode
}

fun parseSensorQr(rawValue: String?): SensorQrCode? {
    val raw = rawValue?.trim()?.uppercase() ?: return null
    return when {
        raw.matches(Regex("LOC:[A-Z]-\\d{2}-\\d{2}")) -> SensorQrCode.Location(raw.removePrefix("LOC:"))
        raw.matches(Regex("PAL:PAL-\\d{3}")) -> SensorQrCode.Pallet(raw.removePrefix("PAL:"))
        else -> null
    }
}

class StabilityTracker(
    private val requiredFrames: Int = STABLE_FRAMES_REQUIRED,
    private val graceFrames: Int = GRACE_FRAMES,
) {
    private var previous: String? = null
    private var frames = 0
    private var missedFrames = 0

    /** Report that [value] was detected in this frame. */
    fun observe(value: String): Int {
        if (value == previous) {
            frames += 1
            missedFrames = 0
        } else {
            previous = value
            frames = 1
            missedFrames = 0
        }
        return frames
    }

    /**
     * Report that the expected code was NOT detected in this frame.
     * Up to [graceFrames] consecutive misses are tolerated without losing
     * stability. On the miss that exceeds the grace threshold the tracker
     * resets completely.
     */
    fun miss() {
        if (previous == null) return
        missedFrames += 1
        if (missedFrames > graceFrames) reset()
    }

    fun reset() {
        previous = null
        frames = 0
        missedFrames = 0
    }

    fun isStable(value: String): Boolean = previous == value && frames >= requiredFrames

    /** Current accumulated frame count (for tests / UI). */
    fun currentFrames(): Int = frames

    /** Current missed-frame count (for tests). */
    fun currentMissed(): Int = missedFrames
}

data class CaptureQuality(
    val score: Int,
    val reasons: Set<String>,
)

data class SensorBox(val left: Float, val top: Float, val right: Float, val bottom: Float) {
    fun width(): Float = right - left
    fun height(): Float = bottom - top
}

enum class DetectionTone { CANDIDATE, CONFIRMED, LOW_QUALITY, INVALID }

data class SensorDetection(
    val rawValue: String,
    val format: String,
    val code: String?,
    val kind: String?,
    val boundingBox: SensorBox,
    val frameWidth: Int,
    val frameHeight: Int,
    val tone: DetectionTone,
    val detail: String,
    val quality: Int? = null,
)

fun calculateCaptureQuality(
    stableFrames: Int,
    boundingBox: SensorBox,
    imageWidth: Int,
    imageHeight: Int,
    brightness: Float,
): CaptureQuality {
    val stability = (min(stableFrames, STABLE_FRAMES_REQUIRED).toFloat() / STABLE_FRAMES_REQUIRED * 40).toInt()
    val fraction = (boundingBox.width() * boundingBox.height()) / (imageWidth * imageHeight).coerceAtLeast(1).toFloat()
    val size = (min(fraction / 0.08f, 1f) * 30).toInt()
    val brightnessDistance = abs(brightness - 0.55f)
    val brightnessScore = (30 - min(30f, brightnessDistance / 0.55f * 30)).toInt()
    val reasons = buildSet {
        if (stableFrames >= STABLE_FRAMES_REQUIRED) add("STABLE_READING") else add("UNSTABLE_READING")
        if (fraction < 0.08f) add("TOO_FAR")
        if (brightness < 0.25f) add("LOW_BRIGHTNESS")
    }
    return CaptureQuality((stability + size + brightnessScore).coerceIn(0, 100), reasons)
}

enum class SensorPhase {
    SEARCHING_LOCATION,
    VALIDATING_LOCATION,
    SEARCHING_PALLET,
    CAPTURING,
    PROCESSING,
    RESULT,
    CAMERA_PERMISSION_REQUIRED,
}

data class SensorUiState(
    val phase: SensorPhase = SensorPhase.SEARCHING_LOCATION,
    val locationCode: String? = null,
    val detectedCode: String? = null,
    val stableFrames: Int = 0,
    val boundingBox: SensorBox? = null,
    val frameWidth: Int = 0,
    val frameHeight: Int = 0,
    val quality: CaptureQuality? = null,
    val previousQuality: Int? = null,
    val message: String = "Buscando código de ubicación",
    val captureRequest: Long = 0,
    val detections: List<SensorDetection> = emptyList(),
)
