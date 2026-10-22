package com.example.d1check.benchmarkrunner

import android.content.Context
import java.io.FileInputStream
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel

object ModelLoader {
    const val ASSET_PATH = "models/mobilenet_v1_1.0_224.tflite"
    const val MODEL_ID = "mobilenet_v1_1.0_224_float"
    const val MODEL_SHA256 = "D95B3C5EA86750CEF882FA867CA357DFE4D265D0B80B67E83277A0BDA310CFBB"

    fun map(context: Context): MappedByteBuffer {
        val descriptor = context.assets.openFd(ASSET_PATH)
        return FileInputStream(descriptor.fileDescriptor).channel.use { channel ->
            channel.map(
                FileChannel.MapMode.READ_ONLY,
                descriptor.startOffset,
                descriptor.declaredLength,
            )
        }.also { descriptor.close() }
    }
}
