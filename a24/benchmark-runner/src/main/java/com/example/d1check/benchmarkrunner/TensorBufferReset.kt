package com.example.d1check.benchmarkrunner

import java.nio.ByteBuffer

internal fun resetTensorBuffers(input: ByteBuffer, output: ByteBuffer) {
    input.rewind()
    output.clear()
}
