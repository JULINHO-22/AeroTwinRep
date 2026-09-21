package com.twobit.aerotwin.core.config

import android.content.Context
import androidx.core.content.edit

class BaseUrlStore(context: Context) {
    private val preferences = context.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    fun load(): String = preferences.getString(KEY_BASE_URL, "").orEmpty()

    fun save(baseUrl: String) {
        preferences.edit { putString(KEY_BASE_URL, baseUrl) }
    }

    private companion object {
        const val PREFERENCES_NAME = "aerotwin_development_config"
        const val KEY_BASE_URL = "base_url"
    }
}
