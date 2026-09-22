package com.mgafk.app.data

import android.util.Log
import com.mgafk.app.BuildConfig

/**
 * Centralized logging wrapper.
 * Debug logs are suppressed in release builds.
 */
object AppLog {

    private val isDebug = BuildConfig.DEBUG

    fun d(tag: String, message: String) {
        NuclearLogStore.recordApp("DEBUG", tag, message)
        if (isDebug) Log.d(tag, message)
    }

    fun w(tag: String, message: String) {
        NuclearLogStore.recordApp("WARN", tag, message)
        Log.w(tag, message)
    }

    fun e(tag: String, message: String, throwable: Throwable? = null) {
        NuclearLogStore.recordApp("ERROR", tag, message, throwable)
        if (throwable != null) {
            Log.e(tag, message, throwable)
        } else {
            Log.e(tag, message)
        }
    }
}
