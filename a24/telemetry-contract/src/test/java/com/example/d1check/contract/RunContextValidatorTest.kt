package com.example.d1check.contract

import org.junit.Test

class RunContextValidatorTest {
    private val initial = D1RunContext("run-a", true, 10L, 20L, "boot-1")

    @Test(expected = RunContextMismatchException::class)
    fun changedRunIsRejected() {
        RunContextValidator.requireSame(
            initial,
            D1RunContext("run-b", true, 30L, 40L, "boot-1"),
            "gpu_load_start",
        )
    }

    @Test(expected = RunContextMismatchException::class)
    fun changedBootIdentifierIsRejected() {
        RunContextValidator.requireSame(
            initial,
            initial.copy(bootId = "boot-2"),
            "before_flush",
        )
    }

    @Test(expected = RunContextMismatchException::class)
    fun inactiveRunIsRejected() {
        RunContextValidator.requireSame(initial, initial.copy(active = false), "warmup_start")
    }
}
