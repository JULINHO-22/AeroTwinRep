package com.twobit.aerotwin.ui.sensor
import android.graphics.Bitmap
import android.graphics.Matrix
import android.graphics.Paint
import android.os.SystemClock
import android.util.Log
import android.util.Size as AndroidSize
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.material3.Text
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.objects.ObjectDetection
import com.google.mlkit.vision.objects.defaults.ObjectDetectorOptions
import com.twobit.aerotwin.core.sensor.*
import java.io.File
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.max

data class CameraBarcodeDetection(val rawValue: String, val format: String, val boundingBox: SensorBox)

@Composable
fun SensorCameraPreview(
    state: SensorUiState,
    onDetections: (List<CameraBarcodeDetection>, Int, Int, Float) -> Unit,
    onImageCaptured: (File) -> Unit,
    onCaptureFailed: () -> Unit,
    modifier: Modifier = Modifier,
    onLiveFrame: (ByteArray) -> Unit = {},
    onObjects: (List<SensorDetection>) -> Unit = {},
    onAnalyzerStatus: (String) -> Unit = {},
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val mainExecutor = remember { ContextCompat.getMainExecutor(context) }
    // Recomposition must never reuse a closed scanner or a shutdown executor.
    val view = remember { PreviewView(context).apply {
        layoutParams = android.view.ViewGroup.LayoutParams(-1, -1)
        scaleType = PreviewView.ScaleType.FILL_CENTER
        implementationMode = PreviewView.ImplementationMode.COMPATIBLE
        keepScreenOn = true
    } }
    val currentDetections by rememberUpdatedState(onDetections)
    val currentObjects by rememberUpdatedState(onObjects)
    val currentLiveFrame by rememberUpdatedState(onLiveFrame)
    val currentStatus by rememberUpdatedState(onAnalyzerStatus)
    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    DisposableEffect(lifecycleOwner, view) {
        val disposed = AtomicBoolean(false)
        val executor = Executors.newSingleThreadExecutor()
        val scanner = BarcodeScanning.getClient(BarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build())
        val objects = ObjectDetection.getClient(ObjectDetectorOptions.Builder()
            .setDetectorMode(ObjectDetectorOptions.STREAM_MODE).enableMultipleObjects().build())
        val providerFuture = ProcessCameraProvider.getInstance(context)
        val preview = Preview.Builder().build().also { it.surfaceProvider = view.surfaceProvider }
        val capture = ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY).build()
        val analysis = ImageAnalysis.Builder().setTargetResolution(AndroidSize(1280, 720))
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
        var frames = 0
        var lastAnalysis = 0L
        var lastPreview = 0L
        var nextObjectAttempt = 0L
        analysis.setAnalyzer(executor) { proxy ->
            val now = SystemClock.elapsedRealtime()
            if (disposed.get() || now - lastAnalysis < 150) proxy.close() else {
                lastAnalysis = now
                try {
                    // Copy with CameraX's stride-aware conversion, then rotate once.
                    val raw = proxy.toBitmap()
                    val rotation = proxy.imageInfo.rotationDegrees
                    val bitmap = if (rotation == 0) raw else Bitmap.createBitmap(raw, 0, 0,
                        raw.width, raw.height, Matrix().apply { postRotate(rotation.toFloat()) }, true)
                    proxy.close()
                    var codes = decodeQrBitmap(bitmap)
                    if (codes.isEmpty()) codes = runCatching {
                        Tasks.await(scanner.process(InputImage.fromBitmap(bitmap, 0)), 2, TimeUnit.SECONDS).mapNotNull { code ->
                            val rect = code.boundingBox ?: return@mapNotNull null
                            val value = code.rawValue ?: return@mapNotNull null
                            CameraBarcodeDetection(value, "QR", SensorBox(rect.left.toFloat(), rect.top.toFloat(), rect.right.toFloat(), rect.bottom.toFloat()))
                        }
                    }.getOrElse { Log.w("AeroTwinSensor", "ML Kit: lector offline sigue activo", it); emptyList() }
                    var objectStatus = ""
                    val boxes = if (now >= nextObjectAttempt) runCatching {
                        Tasks.await(objects.process(InputImage.fromBitmap(bitmap, 0)), 1, TimeUnit.SECONDS).map { obj ->
                            val rect = obj.boundingBox
                            SensorDetection("", "OBJECT", obj.trackingId?.toString(), "OBJETO",
                                SensorBox(rect.left.toFloat(), rect.top.toFloat(), rect.right.toFloat(), rect.bottom.toFloat()),
                                bitmap.width, bitmap.height, DetectionTone.CONFIRMED, "SEGUIMIENTO", null)
                        }
                    }.getOrElse {
                        nextObjectAttempt = now + 10_000
                        objectStatus = " · modelo de objetos iniciando"
                        Log.w("AeroTwinSensor", "Modelo de objetos no disponible", it)
                        emptyList()
                    } else emptyList()
                    frames++
                    val brightness = bitmapBrightness(bitmap)
                    val status = "Visión activa · $frames cuadros · ${codes.size} QR$objectStatus"
                    if (!disposed.get()) mainExecutor.execute {
                        if (!disposed.get()) {
                            currentObjects(boxes)
                            currentDetections(codes, bitmap.width, bitmap.height, brightness)
                            currentStatus(status)
                        }
                    }
                    if (now - lastPreview >= 500) {
                        lastPreview = now
                        val jpeg = previewJpeg(bitmap, boxes, codes)
                        if (!disposed.get()) mainExecutor.execute { if (!disposed.get()) currentLiveFrame(jpeg) }
                    }
                } catch (error: Exception) {
                    runCatching { proxy.close() }
                    Log.e("AeroTwinSensor", "Error de análisis", error)
                    if (!disposed.get()) mainExecutor.execute { currentStatus("Error de cámara: ${error.javaClass.simpleName}") }
                }
            }
        }
        providerFuture.addListener({
            if (!disposed.get()) try {
                val camera = providerFuture.get().bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis, capture)
                view.post {
                    if (!disposed.get() && view.width > 0) camera.cameraControl.startFocusAndMetering(
                        FocusMeteringAction.Builder(view.meteringPointFactory.createPoint(view.width / 2f, view.height / 2f))
                            .setAutoCancelDuration(2, TimeUnit.SECONDS).build())
                }
                imageCapture = capture
            } catch (error: Exception) {
                Log.e("AeroTwinSensor", "No se pudo iniciar CameraX", error)
                currentStatus("No se pudo iniciar cámara: ${error.javaClass.simpleName}")
                onCaptureFailed()
            }
        }, mainExecutor)
        onDispose {
            disposed.set(true)
            imageCapture = null
            analysis.clearAnalyzer()
            if (providerFuture.isDone) runCatching { providerFuture.get().unbind(preview, analysis, capture) }
            executor.execute { scanner.close(); objects.close() }
            executor.shutdown()
            view.keepScreenOn = false
        }
    }
    LaunchedEffect(state.captureRequest, imageCapture) {
        if (state.captureRequest <= 0 || state.phase != SensorPhase.CAPTURING) return@LaunchedEffect
        val capture = imageCapture ?: return@LaunchedEffect
        val output = File(context.cacheDir, "sensor-${System.currentTimeMillis()}.jpg")
        capture.takePicture(ImageCapture.OutputFileOptions.Builder(output).build(), mainExecutor,
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) = onImageCaptured(output)
                override fun onError(exception: ImageCaptureException) = onCaptureFailed()
            })
    }
    AndroidView(factory = { view }, modifier = modifier)
}

private fun bitmapBrightness(bitmap: Bitmap): Float {
    var sum = 0f
    var count = 0
    for (y in 0 until bitmap.height step 30) for (x in 0 until bitmap.width step 30) {
        val pixel = bitmap.getPixel(x, y)
        sum += ((pixel shr 16 and 255) + (pixel shr 8 and 255) + (pixel and 255)) / (3f * 255)
        count++
    }
    return sum / count.coerceAtLeast(1)
}

private fun previewJpeg(bitmap: Bitmap, objects: List<SensorDetection>, codes: List<CameraBarcodeDetection>): ByteArray {
    val scale = minOf(1f, 640f / maxOf(bitmap.width, bitmap.height))
    val frame = Bitmap.createScaledBitmap(bitmap, (bitmap.width * scale).toInt(), (bitmap.height * scale).toInt(), true)
        .copy(Bitmap.Config.ARGB_8888, true)
    val canvas = android.graphics.Canvas(frame)
    val paint = Paint().apply { color = android.graphics.Color.GREEN; strokeWidth = 2f; textSize = 14f }
    fun box(bounds: SensorBox, label: String) {
        paint.style = Paint.Style.STROKE
        canvas.drawRect(bounds.left * scale, bounds.top * scale, bounds.right * scale, bounds.bottom * scale, paint)
        paint.style = Paint.Style.FILL
        canvas.drawText(label, bounds.left * scale, (bounds.top * scale - 5).coerceAtLeast(15f), paint)
    }
    objects.forEach { box(it.boundingBox, "OBJETO ${it.code.orEmpty()}") }
    codes.forEach { box(it.boundingBox, it.rawValue.take(32)) }
    return ByteArrayOutputStream().use { out ->
        frame.compress(Bitmap.CompressFormat.JPEG, 65, out)
        frame.recycle()
        out.toByteArray()
    }
}

@Composable
fun SensorBoundingBox(state: SensorUiState, modifier: Modifier = Modifier) {
    val density = LocalDensity.current
    BoxWithConstraints(modifier) {
        val viewWidth = with(density) { maxWidth.toPx() }
        val viewHeight = with(density) { maxHeight.toPx() }
        Canvas(Modifier.fillMaxSize()) {
        state.detections.forEach { detection ->
            val sourceWidth = detection.frameWidth.takeIf { it > 0 } ?: return@forEach
            val sourceHeight = detection.frameHeight.takeIf { it > 0 } ?: return@forEach
            val scale = max(size.width / sourceWidth, size.height / sourceHeight)
            val offsetX = (size.width - sourceWidth * scale) / 2f
            val offsetY = (size.height - sourceHeight * scale) / 2f
            val box = detection.boundingBox
            val mapped = SensorBox(box.left * scale + offsetX, box.top * scale + offsetY, box.right * scale + offsetX, box.bottom * scale + offsetY)
            val color = when (detection.tone) {
                DetectionTone.CANDIDATE -> Color(0xFF5FA2FF)
                DetectionTone.CONFIRMED -> Color(0xFF35B779)
                DetectionTone.LOW_QUALITY -> Color(0xFFF2B84B)
                DetectionTone.INVALID -> Color(0xFFE05252)
            }
            drawRect(color, Offset(mapped.left, mapped.top), Size(mapped.width(), mapped.height()), style = Stroke(width = 4f))
            val title = detection.kind ?: "CÓDIGO"
            val subtitle = detection.code ?: detection.rawValue.take(18)
            val detail = detection.quality?.let { "$it / 100 · ${detection.detail}" } ?: detection.detail
            val labelTop = (mapped.top - 70f).coerceAtLeast(8f)
            drawRect(Color(0xDD111827), Offset(mapped.left, labelTop), Size(maxOf(170f, mapped.width()), 64f))
        }
        }
        state.detections.forEach { detection ->
            if (detection.frameWidth <= 0 || detection.frameHeight <= 0) return@forEach
            val scale = max(viewWidth / detection.frameWidth, viewHeight / detection.frameHeight)
            val x = detection.boundingBox.left * scale + (viewWidth - detection.frameWidth * scale) / 2f
            val y = (detection.boundingBox.top * scale + (viewHeight - detection.frameHeight * scale) / 2f - 70f).coerceAtLeast(8f)
            val color = when (detection.tone) {
                DetectionTone.CANDIDATE -> Color(0xFF5FA2FF)
                DetectionTone.CONFIRMED -> Color(0xFF35B779)
                DetectionTone.LOW_QUALITY -> Color(0xFFF2B84B)
                DetectionTone.INVALID -> Color(0xFFE05252)
            }
            Column(
                modifier = Modifier.offset(with(density) { x.toDp() }, with(density) { y.toDp() })
                    .background(Color(0xDD111827), RoundedCornerShape(4.dp)).padding(horizontal = 8.dp, vertical = 4.dp),
            ) {
                Text(detection.kind ?: "CÓDIGO", color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Text(detection.code ?: detection.rawValue.take(18), color = color, fontSize = 13.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                Text(detection.quality?.let { "$it / 100 · ${detection.detail}" } ?: detection.detail, color = Color.LightGray, fontSize = 10.sp)
            }
        }

        // --- Continuous active indicator when no QR codes are detected ---
        if (state.detections.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.background(Color(0xDD111827), RoundedCornerShape(8.dp)).padding(12.dp)
                ) {
                    Text("● ANALIZANDO EN TIEMPO REAL", color = Color(0xFF35B779), fontSize = 12.sp, fontWeight = FontWeight.Bold, letterSpacing = 0.5.sp)
                }
            }
        }
    }
}
private fun averageBrightness(imageProxy: androidx.camera.core.ImageProxy): Float {
    val buffer = imageProxy.planes.first().buffer.duplicate()
    val sample = minOf(2000, buffer.remaining()).coerceAtLeast(1)
    var total = 0L; var count = 0
    while (buffer.hasRemaining() && count < sample) { total += buffer.get().toInt() and 0xFF; count++ }
    return total.toFloat() / count / 255f
}
private data class UprightBox(val box: SensorBox, val width: Int, val height: Int)
private fun uprightDimensions(rotation: Int, width: Int, height: Int): Pair<Int, Int> = if (rotation == 90 || rotation == 270) height to width else width to height
private fun rotateBox(box: android.graphics.Rect, rotation: Int, width: Int, height: Int): UprightBox = when (rotation) {
    90 -> UprightBox(SensorBox((height - box.bottom).toFloat(), box.left.toFloat(), (height - box.top).toFloat(), box.right.toFloat()), height, width)
    180 -> UprightBox(SensorBox((width - box.right).toFloat(), (height - box.bottom).toFloat(), (width - box.left).toFloat(), (height - box.top).toFloat()), width, height)
    270 -> UprightBox(SensorBox(box.top.toFloat(), (width - box.right).toFloat(), box.bottom.toFloat(), (width - box.left).toFloat()), height, width)
    else -> UprightBox(SensorBox(box.left.toFloat(), box.top.toFloat(), box.right.toFloat(), box.bottom.toFloat()), width, height)
}
private fun formatName(format: Int): String = when (format) { Barcode.FORMAT_QR_CODE -> "QR"; Barcode.FORMAT_CODE_128 -> "CODE_128"; else -> "OTHER" }
