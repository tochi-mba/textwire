package com.rextechnologies.textwire.protocol

import java.nio.ByteBuffer
import java.nio.charset.CharacterCodingException
import java.nio.charset.CodingErrorAction
import java.nio.charset.StandardCharsets

/** What a document is: the first byte of every envelope (PROTOCOL.md section 4). */
enum class Kind(val code: Int) {
    PAGE(1),
    SEARCH(2),
    STATUS(3),
    HELP(4),
    ;

    companion object {
        fun of(code: Int): Kind? = entries.firstOrNull { it.code == code }
    }
}

/** How the text after the envelope is encoded. */
enum class Codec(val code: Int) {
    NONE(0),
    ZSTD(1),
    ;

    companion object {
        fun of(code: Int): Codec? = entries.firstOrNull { it.code == code }
    }
}

/** The first violated envelope rule; values match the language-neutral golden vectors. */
class EnvelopeException(val fault: String) : IllegalArgumentException(fault)

/** One page of a document, as the phone receives it. */
data class Envelope(val kind: Kind, val page: Int, val pages: Int, val text: String)

const val ENVELOPE_BYTES = 4

/** The envelope in a reassembled payload, or [EnvelopeException] naming the first rule it breaks. */
fun unpackEnvelope(payload: ByteArray, dictionary: ZstdDictionary): Envelope {
    if (payload.size < ENVELOPE_BYTES) throw EnvelopeException("short")
    val kind = Kind.of(payload[0].toInt() and 255) ?: throw EnvelopeException("kind")
    val codec = Codec.of(payload[1].toInt() and 255) ?: throw EnvelopeException("codec")
    val page = payload[2].toInt() and 255
    val pages = payload[3].toInt() and 255
    if (page < 1 || page > pages) throw EnvelopeException("page")
    var body = payload.copyOfRange(ENVELOPE_BYTES, payload.size)
    if (codec == Codec.ZSTD) {
        body = try {
            dictionary.decompress(body)
        } catch (_: CompressionException) {
            throw EnvelopeException("compression")
        }
    }
    val text = try {
        StandardCharsets.UTF_8.newDecoder()
            .onMalformedInput(CodingErrorAction.REPORT)
            .onUnmappableCharacter(CodingErrorAction.REPORT)
            .decode(ByteBuffer.wrap(body))
            .toString()
    } catch (_: CharacterCodingException) {
        throw EnvelopeException("text")
    }
    return Envelope(kind, page, pages, text)
}

/** Join a complete set of one response's frames into its payload, whatever order they came in. */
fun joinFrames(frames: Collection<Frame>): ByteArray {
    require(frames.isNotEmpty()) { "no frames" }
    val total = frames.first().total
    val tag = frames.first().tag
    val bodies = HashMap<Int, List<Byte>>()
    for (frame in frames) {
        require(frame.tag == tag && frame.total == total) { "frames from different responses" }
        val previous = bodies.putIfAbsent(frame.seq, frame.body)
        require(previous == null || previous == frame.body) { "two different copies of frame ${frame.seq}" }
    }
    val missing = (0 until total).filter { it !in bodies }
    require(missing.isEmpty()) { "missing frames ${missing.joinToString(",")}" }
    return (0 until total).flatMap { bodies.getValue(it) }.toByteArray()
}
