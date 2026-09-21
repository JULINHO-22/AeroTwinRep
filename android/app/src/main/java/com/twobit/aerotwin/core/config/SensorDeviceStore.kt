package com.twobit.aerotwin.core.config

import android.content.Context
import androidx.core.content.edit

data class StoredSensorDevice(
    val id: Int,
    val code: String,
    val name: String,
    val token: String,
)

/** Separate storage for the physical-device token; it never stores a human JWT. */
class SensorDeviceStore(context: Context) {
    private val preferences = context.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    fun load(): StoredSensorDevice? {
        val id = preferences.getInt(KEY_ID, 0)
        val code = preferences.getString(KEY_CODE, "").orEmpty()
        val name = preferences.getString(KEY_NAME, "").orEmpty()
        val token = preferences.getString(KEY_TOKEN, "").orEmpty()
        return if (id > 0 && code.isNotBlank() && name.isNotBlank() && token.isNotBlank()) {
            StoredSensorDevice(id, code, name, token)
        } else null
    }

    fun save(device: StoredSensorDevice) {
        preferences.edit {
            putInt(KEY_ID, device.id)
            putString(KEY_CODE, device.code)
            putString(KEY_NAME, device.name)
            putString(KEY_TOKEN, device.token)
        }
    }

    fun clear() = preferences.edit { clear() }

    private companion object {
        const val PREFERENCES_NAME = "aerotwin_sensor_device"
        const val KEY_ID = "sensor_id"
        const val KEY_CODE = "sensor_code"
        const val KEY_NAME = "sensor_name"
        const val KEY_TOKEN = "device_token"
    }
}
