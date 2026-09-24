package com.example.d1check.npurunner

import android.os.SystemClock
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowSystemClock
import java.time.Duration

/**
 * 라운드트립(NpuTimedRunRoundTripTest)이 기대는 전제: 이 모듈(targetSdk 37, JDK 25)에서 Robolectric 이 돌고
 * SystemClock 을 테스트가 진행시킬 수 있다. JDK 25 에는 build.gradle.kts 의 ASM 9.10.1 이 필요하다.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class RobolectricProbeTest {
    @Test
    fun clockIsControllable() {
        val before = SystemClock.elapsedRealtimeNanos()
        ShadowSystemClock.advanceBy(Duration.ofMillis(5))
        assertEquals(5_000_000L, SystemClock.elapsedRealtimeNanos() - before)
    }
}
