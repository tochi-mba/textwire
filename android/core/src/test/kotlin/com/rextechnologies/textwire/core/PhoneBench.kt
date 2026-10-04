package com.rextechnologies.textwire.core

import com.rextechnologies.textwire.protocol.Alphabet
import com.rextechnologies.textwire.protocol.Frame
import com.rextechnologies.textwire.protocol.HEADER_BYTES
import com.rextechnologies.textwire.protocol.ZstdDictionary
import com.rextechnologies.textwire.protocol.decodeFrame
import com.rextechnologies.textwire.protocol.encodeFrame
import com.rextechnologies.textwire.protocol.joinFrames
import com.rextechnologies.textwire.protocol.unpackEnvelope
import java.io.File
import java.util.Base64
import java.util.Locale
import kotlin.system.exitProcess

/** One page of a fixture document, as the server sends it. */
class FixturePage(
    val document: String,
    val cut: String,
    val number: Int,
    val payload: ByteArray,
    val text: String,
) {
    val alphabet: Alphabet get() = if (cut.startsWith("z85g")) Alphabet.Z85G else Alphabet.B64

    /** The SMS texts the page arrives as. */
    fun frames(): List<String> {
        val bodies = payload.toList().chunked(alphabet.frameBytes - HEADER_BYTES)
        return bodies.mapIndexed { seq, body -> encodeFrame(Frame(7, seq, bodies.size, body), alphabet) }
    }
}

/**
 * What the phone does with the replies to every fixture page, timed: the phone half of the
 * performance baseline (`benchmarks/README.md`). Medians in milliseconds, after a warm-up so
 * the JIT has compiled what it will.
 */
object PhoneBench {
    /** How much slower a timing may be before it is reported, as a fraction of the baseline. */
    const val TOLERANCE = 0.5

    fun pages(): List<FixturePage> {
        val text = PhoneBench::class.java.getResource("/pages.tsv")!!.readText()
        val decoder = Base64.getDecoder()
        return text.lines().filter { it.isNotBlank() }.map { line ->
            val (document, cut, number, payload, page) = line.split('\t').map {
                String(decoder.decode(it), Charsets.UTF_8)
            }
            FixturePage(
                document,
                cut,
                number.toInt(),
                payload.chunked(2).map { it.toInt(16).toByte() }.toByteArray(),
                page,
            )
        }
    }

    fun timed(repeats: Int, run: () -> Unit): Double {
        repeat(maxOf(1, repeats / 3)) { run() }
        val samples = List(repeats) {
            val start = System.nanoTime()
            run()
            (System.nanoTime() - start) / 1e6
        }.sorted()
        return Math.round(samples[samples.size / 2] * 10_000) / 10_000.0
    }

    fun measure(repeats: Int = 25): Map<String, Double> {
        val pages = pages()
        val frames = pages.map { it.frames() }
        val dictionary = ZstdDictionary.packaged()
        return linkedMapOf(
            "load_dictionary_ms" to timed(repeats) { ZstdDictionary.packaged() },
            "decode_frames_ms" to timed(repeats) { frames.forEach { page -> page.forEach(::decodeFrame) } },
            "decompress_pages_ms" to timed(repeats) { pages.forEach { unpackEnvelope(it.payload, dictionary) } },
            "parse_pages_ms" to timed(repeats) { pages.forEach { parseDocument(it.text) } },
            "receive_every_page_ms" to timed(repeats) {
                for (page in frames) parseDocument(unpackEnvelope(joinFrames(page.map(::decodeFrame)), dictionary).text)
            },
        )
    }

    /** Each timing that moved by more than [TOLERANCE], as `name: before -> after (worse)`. */
    fun compare(before: Map<String, Double>, after: Map<String, Double>): List<String> =
        before.keys.intersect(after.keys).sorted().mapNotNull { name ->
            val old = before.getValue(name)
            val new = after.getValue(name)
            if (kotlin.math.abs(new - old) <= old * TOLERANCE) {
                null
            } else {
                "$name: $old -> $new (${if (new > old) "worse" else "better"})"
            }
        }

    /** A result as JSON: the machine and the timings, keys in order, one per line. */
    fun json(speed: Map<String, Double>): String {
        val machine = "\"java\": \"${System.getProperty("java.version")}\", " +
            "\"system\": \"${System.getProperty("os.name")} ${System.getProperty("os.version")}\""
        val timings = speed.entries.joinToString(",\n") { (name, value) ->
            "    \"$name\": ${String.format(Locale.ROOT, "%.4f", value)}"
        }
        return "{\n  \"machine\": {$machine},\n  \"speed\": {\n$timings\n  }\n}\n"
    }

    /** The timings out of a result [json] wrote. */
    fun speed(json: String): Map<String, Double> {
        val block = json.substringAfter("\"speed\": {").substringBefore("}")
        val timing = Regex("""\"(\w+)\": ([0-9.]+)""")
        return timing.findAll(block).associate { it.groupValues[1] to it.groupValues[2].toDouble() }
    }
}

/** `bench <baseline> record|compare`: write the baseline, or print what moved since it. */
fun main(args: Array<String>) {
    val baseline = File(args[0])
    val now = PhoneBench.measure()
    for ((name, value) in now) println("  ${name.padEnd(24)} ${String.format(Locale.ROOT, "%10.4f", value)}")
    if (args[1] == "record") {
        baseline.writeText(PhoneBench.json(now))
        println("recorded ${baseline.name}")
        return
    }
    if (!baseline.isFile) {
        println("no baseline at ${baseline.path}; run make bench-record first")
        exitProcess(1)
    }
    val changes = PhoneBench.compare(PhoneBench.speed(baseline.readText()), now)
    changes.forEach { println("  $it") }
    val verdict = if (changes.isEmpty()) {
        "every timing within tolerance of ${baseline.name}"
    } else {
        "${changes.size} timing(s) moved"
    }
    println(verdict)
}
