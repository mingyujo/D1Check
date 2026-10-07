package com.example.d1check.requestrunner

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * K4: A24 ExplicitDetectionDecoderTest 이식 + fixture (무작위 50 + 경계 사례, Python d1_detection_contract.decode 가 기대값) +
 * 실제 raw 출력 (local_inputs/reference_pc/detection/output_{0,1}.f32le, ai-edge-litert 2.2.0 CPU) → Kotlin 디코더 == golden.json decoded.
 */
class DecodersTest {
    @Test fun a24YxhwLabelOffsetAndOriginalCoordinates() {
        val result = DetectionDecoder.decode(floatArrayOf(.1f, .75f), floatArrayOf(.5f, -.25f, 0f, 0f),
            listOf(doubleArrayOf(.5, .5, .4, .2)), listOf("a", "b"), 100, 200).single()
        assertEquals("b", result.label)
        listOf(20.0, 100.0, 40.0, 40.0).forEachIndexed { i, v -> assertEquals(v, result.box[i], 1e-8) }
    }

    @Test fun a24FixedThresholdNmsAndTieRules() {
        val results = DetectionDecoder.decode(floatArrayOf(.5f, .1f, .1f, .7f), FloatArray(8),
            List(2) { doubleArrayOf(.5, .5, .2, .2) }, listOf("a", "b"), 100, 100)
        assertEquals(1, results.size)
        assertEquals("b", results.single().label)
        val threshold = DetectionDecoder.decode(floatArrayOf(.5f, .5f), FloatArray(4), listOf(doubleArrayOf(.5, .5, 1.0, 1.0)), listOf("a", "b"), 1, 1)
        assertEquals("a", threshold.single().label)
    }

    @Test fun a24MalformedAndNonfiniteFailClosed() {
        assertThrows(IllegalArgumentException::class.java) {
            DetectionDecoder.decode(floatArrayOf(Float.NaN), FloatArray(4), listOf(doubleArrayOf(.5, .5, 1.0, 1.0)), listOf("a"), 1, 1)
        }
        assertThrows(IllegalArgumentException::class.java) {
            DetectionDecoder.decode(floatArrayOf(.5f), FloatArray(3), listOf(doubleArrayOf(.5, .5, 1.0, 1.0)), listOf("a"), 1, 1)
        }
    }

    @Test fun classificationTop5OrdersByScoreThenIndexAndRejectsNonFinite() {
        val labels = List(6) { "c$it" }
        val top = ClassificationDecoder.top5(floatArrayOf(0.1f, 0.5f, 0.5f, 0.05f, 0.9f, 0.5f), labels)
        assertEquals(listOf(4, 1, 2, 5, 0), top.map { it.classIndex })
        assertEquals(listOf("c4", "c1", "c2", "c5", "c0"), top.map { it.label })
        assertThrows(IllegalArgumentException::class.java) { ClassificationDecoder.top5(floatArrayOf(Float.POSITIVE_INFINITY, 0f), listOf("a", "b")) }
        assertThrows(IllegalArgumentException::class.java) { ClassificationDecoder.top5(floatArrayOf(0f), listOf("a", "b")) }
    }

    @Test fun fixtureCasesAgreeWithThePythonDecoder() {
        val text = javaClass.classLoader!!.getResource("decode_cases_v1.json")?.readText()
            ?: File("src/test/resources/decode_cases_v1.json").readText()
        val cases = TestJson.parse(text).let { (it as Map<*, *>)["cases"] as List<*> }
        assertTrue(cases.size >= 56)
        var detections = 0
        for (raw in cases) {
            val case = raw as Map<*, *>
            val name = case["name"] as String
            val labels = (case["labels"] as List<*>).map { it as String }
            val anchors = (case["anchors"] as List<*>).map { a -> (a as List<*>).map { (it as Number).toDouble() }.toDoubleArray() }
            val scores = (case["scores"] as List<*>).map { (it as Number).toFloat() }.toFloatArray()
            val locations = (case["locations"] as List<*>).map { (it as Number).toFloat() }.toFloatArray()
            val expected = (case["expected"] as List<*>).map { it as Map<*, *> }
            val actual = DetectionDecoder.decode(scores, locations, anchors, labels, (case["width"] as Number).toInt(), (case["height"] as Number).toInt())
            assertEquals(name, expected.size, actual.size)
            expected.zip(actual).forEach { (e, a) ->
                assertEquals(name, e["label"], a.label)
                assertEquals(name, (e["score"] as Number).toDouble(), a.score, 0.0)
                val box = (e["box"] as List<*>).map { (it as Number).toDouble() }
                for (i in 0..3) assertEquals("$name box[$i]", box[i], a.box[i], 1e-9 * maxOf(1.0, Math.abs(box[i])))
            }
            detections += actual.size
        }
        assertTrue("fixture is degenerate: $detections detections", detections > 20)
        val names = cases.map { (it as Map<*, *>)["name"] }
        for (n in listOf("score_tie_two_anchors", "iou_at_0_3_boundary", "empty_result", "score_threshold_edge", "class_tie_first_index")) assertTrue(n, n in names)
    }

    private fun f32le(file: File): FloatArray {
        val bytes = file.readBytes()
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(bytes.size / 4).also { buffer.get(it) }
    }

    @Test fun realRawOutputsDecodeToTheA24PcGolden() {
        val root = File("../local_inputs/reference_pc")
        assumeTrue("local_inputs/reference_pc missing (git 밖)", File(root, "detection/golden.json").isFile)
        val golden = TestJson.parse(File(root, "detection/golden.json").readText()) as Map<*, *>
        val scores = f32le(File(root, "detection/output_0.f32le"))
        val boxes = f32le(File(root, "detection/output_1.f32le"))
        assertEquals(19206 * 90, scores.size)
        assertEquals(19206 * 4, boxes.size)
        val anchors = (TestJson.parse(File(root, "anchors.json").readText()) as List<*>).map { a -> (a as List<*>).map { (it as Number).toDouble() }.toDoubleArray() }
        assertEquals(19206, anchors.size)
        val labels = TaskRuntime.labelLines(File(root, "labels.txt").readText())
        assertEquals(90, labels.size)
        val size = golden["image_size"] as List<*>
        val actual = DetectionDecoder.decode(scores, boxes, anchors, labels, (size[0] as Number).toInt(), (size[1] as Number).toInt())
        val expected = (golden["decoded"] as List<*>).map { it as Map<*, *> }
        assertEquals(expected.size, actual.size)
        assertTrue(actual.isNotEmpty())
        expected.zip(actual).forEach { (e, a) ->
            assertEquals(e["label"], a.label)
            assertEquals((e["score"] as Number).toDouble(), a.score, 0.0)
            val box = (e["box"] as List<*>).map { (it as Number).toDouble() }
            for (i in 0..3) assertEquals(box[i], a.box[i], 1e-9 * maxOf(1.0, Math.abs(box[i])))
        }
        // classification golden: top-5 from the PC raw output through the Kotlin decoder
        val clsGolden = TestJson.parse(File(root, "classification/golden.json").readText()) as Map<*, *>
        val softmax = f32le(File(root, "classification/output_0.f32le"))
        val clsLabels = TaskRuntime.labelLines(File(root, "labels_without_background.txt").readText())
        val top5 = ClassificationDecoder.top5(softmax, clsLabels)
        val results = (clsGolden["results"] as List<*>).map { it as Map<*, *> }
        assertEquals(results.map { it["label"] }, top5.map { it.label })
        assertEquals(results.map { (it["class_index"] as Number).toInt() }, top5.map { it.classIndex })
        results.zip(top5).forEach { (r, t) -> assertEquals((r["score"] as Number).toDouble(), t.score.toDouble(), 0.0) }
        assertEquals("crash helmet", top5[0].label)
        assertEquals(518, top5[0].classIndex)
    }
}
