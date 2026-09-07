package com.example.d1check.benchmarkrunner

import android.os.Build
import android.util.Log
import org.json.JSONObject

internal data class NnapiDeviceInfo(
    val index: Int,
    val name: String,
    val typeNumber: Int,
    val version: String,
    val featureLevel: Long,
) {
    val typeName: String
        get() = NnapiDeviceProbe.typeName(typeNumber)

    val isReferenceCpu: Boolean
        get() = name.equals("nnapi-reference", ignoreCase = true)
}

internal sealed interface NnapiProbeResult {
    data class Unsupported(val apiLevel: Int) : NnapiProbeResult
    data class Success(val devices: List<NnapiDeviceInfo>) : NnapiProbeResult
}

internal object NnapiDeviceProbe {
    private const val TAG = "D1NPU"
    private const val SCHEMA_VERSION = 1
    private const val FIELDS_PER_DEVICE = 5

    @Volatile
    private var nativeLibraryLoaded = false

    fun probeAndLog(apiLevel: Int = Build.VERSION.SDK_INT): NnapiProbeResult {
        if (!isSupportedApiLevel(apiLevel)) {
            return NnapiProbeResult.Unsupported(apiLevel)
        }

        ensureNativeLibraryLoaded()
        val devices = decodeNativeDevices(nativeEnumerateDevices())
        devices.forEach { device -> Log.i(TAG, toJson(device)) }
        return NnapiProbeResult.Success(devices)
    }

    internal fun isSupportedApiLevel(apiLevel: Int): Boolean =
        apiLevel >= Build.VERSION_CODES.Q

    internal fun typeName(typeNumber: Int): String = when (typeNumber) {
        0 -> "UNKNOWN"
        1 -> "OTHER"
        2 -> "CPU"
        3 -> "GPU"
        4 -> "ACCELERATOR"
        else -> "UNKNOWN"
    }

    internal fun decodeNativeDevices(values: Array<String>): List<NnapiDeviceInfo> {
        require(values.size % FIELDS_PER_DEVICE == 0) {
            "Malformed native NNAPI response: ${values.size} values"
        }
        return values.asList().chunked(FIELDS_PER_DEVICE).map { fields ->
            NnapiDeviceInfo(
                index = fields[0].toInt(),
                name = fields[1],
                typeNumber = fields[2].toInt(),
                version = fields[3],
                featureLevel = fields[4].toLong(),
            )
        }
    }

    private fun toJson(device: NnapiDeviceInfo): String = JSONObject()
        .put("schema_version", SCHEMA_VERSION)
        .put("event", "nnapi_device")
        .put("index", device.index)
        .put("name", device.name)
        .put("type_number", device.typeNumber)
        .put("type_name", device.typeName)
        .put("version", device.version)
        .put("feature_level", device.featureLevel)
        .put("reference_cpu", device.isReferenceCpu)
        .put("npu_verification", "UNVERIFIED")
        .toString()

    @Synchronized
    private fun ensureNativeLibraryLoaded() {
        if (!nativeLibraryLoaded) {
            System.loadLibrary("d1_npu_probe")
            nativeLibraryLoaded = true
        }
    }

    private external fun nativeEnumerateDevices(): Array<String>
}
