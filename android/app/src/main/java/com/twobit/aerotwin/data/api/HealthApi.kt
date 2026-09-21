package com.twobit.aerotwin.data.api

import com.google.gson.annotations.SerializedName
import java.util.concurrent.TimeUnit
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET

data class HealthResponse(
    @SerializedName("status") val status: String,
    @SerializedName("environment") val environment: String?,
)

interface HealthApi {
    @GET("api/v1/health")
    suspend fun getHealth(): HealthResponse
}

object HealthApiFactory {
    private const val TIMEOUT_SECONDS = 6L

    fun create(baseUrl: String): HealthApi {
        val client = OkHttpClient.Builder()
            .connectTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .readTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .writeTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .build()

        return Retrofit.Builder()
            .baseUrl(normalizeBaseUrl(baseUrl))
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(HealthApi::class.java)
    }

    fun normalizeBaseUrl(rawBaseUrl: String): String {
        val trimmed = rawBaseUrl.trim()
        require(trimmed.isNotEmpty()) { "Escribe la dirección del backend." }
        require(trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            "La dirección debe comenzar con http:// o https://"
        }
        return if (trimmed.endsWith('/')) trimmed else "$trimmed/"
    }
}

