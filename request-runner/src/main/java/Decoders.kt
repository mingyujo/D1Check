package com.example.d1check.requestrunner

import kotlin.math.exp

/*
 * 출처: feature/arrival-scheduling-20260923 @ d588323
 *   benchmark-runner/src/modelProbe/.../ProbeTaskAdapter.kt 65~68행 (분류 top-5: 점수 내림차순 → index 오름차순)
 *   benchmark-runner/src/modelProbe/.../ProbeTaskAdapter.kt 89~123행 (ExplicitDetectionDecoder — anchor 별 argmax (동점 첫 index) ·
 *     score ≥ 0.5 · yxhw → xywh 비클립 · 사전 정렬 score↓ then anchor index · class-agnostic greedy NMS IoU > 0.3 억제 ·
 *     최종 정렬 score↓, label, box)
 * Python 대응 = tools/d1_detection_contract.decode (같은 규칙). 값 · 순서를 바꾸지 않았다.
 */
object ClassificationDecoder {
    const val TOP_K = 5

    data class Item(val label: String, val classIndex: Int, val score: Float)

    fun top5(softmax: FloatArray, labels: List<String>): List<Item> {
        require(softmax.size == labels.size) { "softmax/labels size" }
        require(softmax.all { it.isFinite() }) { "non-finite classification output" }
        return softmax.indices.sortedWith(compareByDescending<Int> { softmax[it] }.thenBy { it }).take(TOP_K)
            .map { i -> Item(labels[i], i, softmax[i]) }
    }

    fun toMaps(items: List<Item>): List<Map<String, Any?>> =
        items.map { linkedMapOf("label" to it.label, "class_index" to it.classIndex, "score" to it.score) }
}

object DetectionDecoder {
    const val SCORE_THRESHOLD = 0.5
    const val NMS_IOU = 0.3
    const val ID = "efficientdet-metadata-yxhw-nms-v1"

    private data class Candidate(val index: Int, val label: String, val score: Double, val box: DoubleArray)

    data class Detection(val label: String, val score: Double, val box: DoubleArray)

    fun decode(
        scores: FloatArray,
        locations: FloatArray,
        anchors: List<DoubleArray>,
        labels: List<String>,
        width: Int,
        height: Int,
    ): List<Detection> {
        require(width > 0 && height > 0 && labels.isNotEmpty()) { "decoder geometry" }
        require(scores.size == anchors.size * labels.size && locations.size == anchors.size * 4) { "decoder tensor mismatch" }
        require(scores.all { it.isFinite() } && locations.all { it.isFinite() }) { "non-finite decoder input" }
        val candidates = anchors.mapIndexedNotNull { i, a ->
            require(a.size == 4 && a.all { it.isFinite() } && a[2] > 0 && a[3] > 0) { "anchor $i" }
            var cls = 0
            for (j in 1 until labels.size) if (scores[i * labels.size + j] > scores[i * labels.size + cls]) cls = j
            val score = scores[i * labels.size + cls].toDouble()
            if (score < SCORE_THRESHOLD) return@mapIndexedNotNull null
            val cx = locations[i * 4 + 1] * a[2] + a[0]
            val cy = locations[i * 4] * a[3] + a[1]
            val w = exp(locations[i * 4 + 3].toDouble()) * a[2]
            val h = exp(locations[i * 4 + 2].toDouble()) * a[3]
            val box = doubleArrayOf((cx - w / 2) * width, (cy - h / 2) * height, w * width, h * height)
            require(box.all { it.isFinite() } && w > 0 && h > 0) { "invalid decoded box" }
            Candidate(i, labels[cls], score, box)
        }.sortedWith(compareByDescending<Candidate> { it.score }.thenBy { it.index })
        val accepted = mutableListOf<Candidate>()
        for (candidate in candidates) if (accepted.all { iou(it.box, candidate.box) <= NMS_IOU }) accepted += candidate
        return accepted.sortedWith(
            compareByDescending<Candidate> { it.score }.thenBy { it.label }
                .thenBy { it.box[0] }.thenBy { it.box[1] }.thenBy { it.box[2] }.thenBy { it.box[3] },
        ).map { Detection(it.label, it.score, it.box) }
    }

    fun iou(a: DoubleArray, b: DoubleArray): Double {
        val intersection = maxOf(0.0, minOf(a[0] + a[2], b[0] + b[2]) - maxOf(a[0], b[0])) *
            maxOf(0.0, minOf(a[1] + a[3], b[1] + b[3]) - maxOf(a[1], b[1]))
        val union = a[2] * a[3] + b[2] * b[3] - intersection
        return if (union > 0) intersection / union else 0.0
    }

    fun toMaps(items: List<Detection>): List<Map<String, Any?>> =
        items.map { linkedMapOf("label" to it.label, "score" to it.score, "box" to it.box.toList()) }
}
