package com.twobit.aerotwin.ui.sensor

import android.graphics.Bitmap
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.RGBLuminanceSource
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.multi.qrcode.QRCodeMultiReader
import com.twobit.aerotwin.core.sensor.SensorBox

/** Offline QR decoder also exercised by instrumentation against real photographs. */
fun decodeQrBitmap(bitmap: Bitmap): List<CameraBarcodeDetection> {
    val pixels = IntArray(bitmap.width * bitmap.height)
    bitmap.getPixels(pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
    val source = RGBLuminanceSource(bitmap.width, bitmap.height, pixels)
    val hints = mapOf<DecodeHintType, Any>(DecodeHintType.TRY_HARDER to true)
    return runCatching {
        QRCodeMultiReader().decodeMultiple(BinaryBitmap(HybridBinarizer(source)), hints).map { result ->
            val points = result.resultPoints
            CameraBarcodeDetection(result.text, "QR", SensorBox(
                points.minOf { it.x }, points.minOf { it.y },
                points.maxOf { it.x }, points.maxOf { it.y },
            ))
        }
    }.getOrDefault(emptyList())
}
