package com.twobit.aerotwin.core.config

import android.content.Context

class SessionStore(context: Context) {
    private val preferences = context.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    fun loadToken(): String = preferences.getString(KEY_TOKEN, "").orEmpty()

    fun saveToken(token: String) {
        preferences.edit().putString(KEY_TOKEN, token).apply()
    }

    fun clear() {
        preferences.edit().remove(KEY_TOKEN).apply()
    }

    private companion object {
        const val PREFERENCES_NAME = "aerotwin_private_session"
        const val KEY_TOKEN = "access_token"
    }
}
