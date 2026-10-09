package com.example.d1check.requestrunner

import com.example.d1check.requestrunner.MixreqContract.Request
import org.json.JSONObject

/**
 * 호스트 (s26/tools/mixreq/mixreq_plan.py) 가 만드는 세션 manifest. 앱은 값을 믿지 않고 계약과 다시 대조한다 (fail closed):
 * 정책 ∈ 블록 · 상주 runtime 키 = 블록 키 집합 정확히 · 요청표 = uuid5 유도와 동일 · 단계 길이 = 계약 상수 · 표본 900 ms.
 */
class SessionManifest(
    val protocol: String,
    val experimentId: String,
    val split: String,
    val sessionId: String,
    val sessionIndex: Int,
    val block: String,
    val pair: Int,
    val attempt: Int,
    val policy: String,
    val runtimes: List<RuntimeSpec>,
    val image: FileSpec,
    val imageWidth: Int,
    val imageHeight: Int,
    val anchors: FileSpec,
    val labels: Map<String, FileSpec>,
    val requests: List<Request>,
    val phases: Phases,
    val samplePeriodMs: Long,
    val timeScale: Int,
    val warmupGate: Boolean,
    val stopRules: StopRules,
    val startThermalStatusMax: Int,
    /** diagnostic 전용 (스모크 S1): runtime 생성 + warmup 만 하고 끝낸다 (등록 §3-8 "S1 = 블록 N 구성 warmup 10"). */
    val warmupOnly: Boolean = false,
) {
    data class FileSpec(val path: String, val sha256: String) {
        init { require(sha256.matches(Regex("[a-f0-9]{64}"))) { "sha256 of $path" } }
    }

    data class Phases(val setupS: Long, val gateS: Long, val baselineS: Long, val commonS: Long, val drainS: Long, val coolingS: Long)

    /** 등록 §3-6 앱 안 멈춤: plugged ≠ 0 · thermal status ≥ 3 · BAT ≥ 42.0 ℃ · SOC < 20 · 화면 꺼짐. */
    data class StopRules(val batteryDeciCMax: Int, val thermalStatusMax: Int, val socMin: Int)

    val usedKeys: Set<String> get() = MixreqContract.usedKeys(policy)
    val setupNs: Long get() = phases.setupS * 1_000_000_000L

    fun validate() {
        require(protocol == MixreqContract.PROTOCOL) { "protocol $protocol" }
        require(split == MixreqContract.SPLIT_CONFIRMATION || split == MixreqContract.SPLIT_DIAGNOSTIC) { "split $split" }
        // v3 (등록 v3 §0-1 · §0-2): 실험 ID 는 표에 있어야 하고 (fail closed), 요청 수 · 공통창 · index 범위는 그 표 행의 값이어야 한다.
        val experiment = MixreqContract.experimentOf(experimentId)
        MixreqContract.activeExperiment = experiment
        require(Uuid5.isCanonical(sessionId)) { "session_id" }
        require(block == MixreqContract.BLOCK_A || block == MixreqContract.BLOCK_N) { "block $block" }
        require(policy in MixreqContract.policiesOf(block)) { "policy $policy is not allowed in block $block" }
        require(attempt in 1..2) { "attempt $attempt" }
        require(sessionIndex in 0..experiment.sessionIndexMax && pair in 0..3) { "session_index/pair" }
        val keys = runtimes.map { it.key }
        require(keys.toSet() == MixreqContract.keysOf(block) && keys.size == keys.toSet().size) {
            "runtimes $keys != block $block keys"
        }
        runtimes.forEach { spec ->
            if (spec.backend == Backend.NPU) require(spec.modelId.endsWith("_Samsung_E9965")) { "NPU runtime must open an AOT artifact" }
            else require(!spec.modelId.endsWith("_Samsung_E9965")) { "AOT artifact is NPU-only (${spec.key})" }
            if (spec.backend == Backend.GPU) require(spec.gpuPrecision == "FP32") { "GPU precision must be FP32 (${spec.key})" }
        }
        require(labels.keys == setOf("classification", "detection")) { "labels" }
        require(imageWidth in 1..4096 && imageHeight in 1..4096) { "image size" }
        MixreqContract.validateRequests(requests, requests.size)
        RequestPlan.requireDerived(experimentId, sessionIndex, sessionId, requests)
        if (split == MixreqContract.SPLIT_CONFIRMATION) {
            require(experimentId == experiment.id) { "confirmation experiment_id" }
            require(requests.size == experiment.requestCount) { "confirmation needs ${experiment.requestCount} requests" }
            require(timeScale == 1) { "confirmation needs time_scale 1" }
            require(!warmupOnly) { "confirmation cannot be warmup_only" }
        } else {
            require(timeScale in 1..100) { "time_scale" }
        }
        require(phases.commonS == experiment.commonS && phases.baselineS == MixreqContract.BASELINE_SECONDS &&
            phases.drainS == MixreqContract.DRAIN_SECONDS && phases.coolingS == MixreqContract.COOLING_SECONDS &&
            phases.gateS == MixreqContract.GATE_NS / 1_000_000_000L) { "phase lengths must equal the contract" }
        require(phases.setupS * 1_000_000_000L == MixreqContract.setupNsOf(block)) { "setup_s for block $block" }
        require(samplePeriodMs == MixreqContract.SAMPLE_PERIOD_MS) { "sample_period_ms" }
        require(stopRules.batteryDeciCMax == 420 && stopRules.thermalStatusMax == 2 && stopRules.socMin == 20) { "stop_rules" }
        require(startThermalStatusMax == 1) { "start_check thermal_status_max" }
    }

    companion object {
        fun parse(text: String): SessionManifest {
            val m = JSONObject(text)
            val runtimesJson = m.getJSONArray("runtimes")
            val runtimes = (0 until runtimesJson.length()).map { i ->
                val r = runtimesJson.getJSONObject(i)
                RuntimeSpec(
                    key = r.getString("key"),
                    task = r.getString("task"),
                    backend = Backend.valueOf(r.getString("backend")),
                    modelPath = r.getString("model_path"),
                    modelSha256 = r.getString("model_sha256"),
                    // optString would return the string "null" for a JSON null (org.json) -> check isNull explicitly
                    gpuPrecision = if (r.has("gpu_precision") && !r.isNull("gpu_precision")) r.getString("gpu_precision").ifEmpty { null } else null,
                    cpuThreads = if (r.has("cpu_threads") && !r.isNull("cpu_threads")) r.getInt("cpu_threads") else null,
                )
            }
            val requestsJson = m.getJSONArray("requests")
            val requests = (0 until requestsJson.length()).map { i ->
                val q = requestsJson.getJSONObject(i)
                Request(q.getString("request_id"), q.getInt("ordinal"), q.getString("task_id"), q.getString("priority"),
                    q.getLong("offset_ms"), q.getLong("deadline_ms"))
            }
            val image = m.getJSONObject("image")
            val anchors = m.getJSONObject("anchors")
            val labelsJson = m.getJSONObject("labels")
            val labels = labelsJson.keys().asSequence().associateWith { k ->
                val l = labelsJson.getJSONObject(k)
                FileSpec(l.getString("path"), l.getString("sha256"))
            }
            val p = m.getJSONObject("phases")
            val s = m.getJSONObject("stop_rules")
            return SessionManifest(
                protocol = m.getString("protocol"),
                experimentId = m.getString("experiment_id"),
                split = m.getString("split"),
                sessionId = m.getString("session_id"),
                sessionIndex = m.getInt("session_index"),
                block = m.getString("block"),
                pair = m.getInt("pair"),
                attempt = m.getInt("attempt"),
                policy = m.getString("policy"),
                runtimes = runtimes,
                image = FileSpec(image.getString("path"), image.getString("sha256")),
                imageWidth = image.getInt("width"),
                imageHeight = image.getInt("height"),
                anchors = FileSpec(anchors.getString("path"), anchors.getString("sha256")),
                labels = labels,
                requests = requests,
                phases = Phases(p.getLong("setup_s"), p.getLong("gate_s"), p.getLong("baseline_s"), p.getLong("common_s"),
                    p.getLong("drain_s"), p.getLong("cooling_s")),
                samplePeriodMs = m.getLong("sample_period_ms"),
                timeScale = m.optInt("time_scale", 1),
                warmupGate = m.optBoolean("warmup_gate", true),
                stopRules = StopRules(s.getInt("battery_deci_c_max"), s.getInt("thermal_status_max"), s.getInt("soc_min")),
                startThermalStatusMax = m.getJSONObject("start_check").getInt("thermal_status_max"),
                warmupOnly = m.optBoolean("warmup_only", false),
            )
        }
    }
}
