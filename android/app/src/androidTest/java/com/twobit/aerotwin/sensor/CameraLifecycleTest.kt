package com.twobit.aerotwin.sensor

import android.Manifest
import android.content.Intent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.runtime.mutableStateOf
import androidx.test.platform.app.InstrumentationRegistry
import com.twobit.aerotwin.MainActivity
import com.twobit.aerotwin.core.sensor.SensorUiState
import com.twobit.aerotwin.core.sensor.SensorPhase
import com.twobit.aerotwin.ui.sensor.SensorCameraPreview
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import org.junit.Assert.assertTrue
import org.junit.Test

class CameraLifecycleTest {
    @Test fun analyzesAndStreamsAfterCameraIsReopened() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        instrumentation.uiAutomation.grantRuntimePermission(context.packageName, Manifest.permission.CAMERA)
        val activity = instrumentation.startActivitySync(Intent(context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) as ComponentActivity
        try {
            repeat(2) {
                val preview = CountDownLatch(2)
                val capture = CountDownLatch(1)
                val sensorState = mutableStateOf(SensorUiState())
                val status = AtomicReference("No analyzer callback")
                instrumentation.runOnMainSync {
                    activity.setContent {
                        SensorCameraPreview(sensorState.value, { _, _, _, _ -> }, { file ->
                            if (file.length() > 100) capture.countDown()
                            file.delete()
                        }, { },
                            modifier = Modifier.fillMaxSize(),
                            onLiveFrame = { jpeg -> if (jpeg.size > 100) preview.countDown() },
                            onAnalyzerStatus = { status.set(it) })
                    }
                }
                assertTrue("Camera must analyze and stream after opening: ${status.get()}", preview.await(25, TimeUnit.SECONDS))
                instrumentation.runOnMainSync {
                    sensorState.value = SensorUiState(phase = SensorPhase.CAPTURING, captureRequest = 1)
                }
                assertTrue("Camera must take evidence automatically", capture.await(15, TimeUnit.SECONDS))
                instrumentation.runOnMainSync { activity.setContent { } }
                instrumentation.waitForIdleSync()
            }
        } finally { instrumentation.runOnMainSync { activity.finish() } }
    }
}
