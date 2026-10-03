package com.rextechnologies.textwire.protocol

import java.util.Base64

/** Text encodings that keep each character inside the GSM-7 basic alphabet. */
enum class Alphabet(val frameBytes: Int) {
    B64(120),
    Z85G(127),
}

/** The first violated wire rule; values match the language-neutral golden vectors. */
class FrameException(val fault: String) : IllegalArgumentException(fault)

/** A decoded frame. Byte lists provide structural equality across test and app boundaries. */
data class Frame(val tag: Int, val seq: Int, val total: Int, val body: List<Byte>)

private const val SYMBOLS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-:+=\"!/*?&<>()',;@%$#_"
private val BASE64_PATTERN = Regex("[A-Za-z0-9_-]*")

/** CRC-8/SMBUS over the five identifying header bytes and payload body. */
fun crc8(bytes: List<Byte>): Int {
    var crc = 0
    for (byte in bytes) crc = CRC_TABLE[crc xor (byte.toInt() and 255)]
    return crc
}

/** The CRC of every single byte, so the checksum takes one lookup a byte instead of eight steps. */
private val CRC_TABLE = IntArray(256) { byte ->
    var crc = byte
    repeat(8) { crc = if (crc and 128 != 0) ((crc shl 1) xor 7) and 255 else (crc shl 1) and 255 }
    crc
}

private fun encodeBytes(bytes: ByteArray, alphabet: Alphabet): String {
    if (alphabet == Alphabet.B64) return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
    return buildString {
        append('.')
        for (block in bytes.asList().chunked(4)) {
            var value = 0L
            for (index in 0 until 4) {
                val byte = if (index < block.size) block[index].toInt() and 255 else 0
                value = (value shl 8) or byte.toLong()
            }
            val digits = CharArray(5)
            for (index in 4 downTo 0) {
                digits[index] = SYMBOLS[(value % 85).toInt()]
                value /= 85
            }
            append(digits.concatToString().take(block.size + 1))
        }
    }
}

private fun decodeBytes(text: String, alphabet: Alphabet): ByteArray {
    val bytes = if (alphabet == Alphabet.B64) {
        if (!BASE64_PATTERN.matches(text) || text.length % 4 == 1) throw FrameException("encoding")
        Base64.getUrlDecoder().decode(text)
    } else {
        val encoded = text.drop(1)
        if (encoded.any { it !in SYMBOLS } || encoded.length % 5 == 1) throw FrameException("encoding")
        encoded.chunked(5).flatMap { chunk ->
            var value = 0L
            for (char in chunk.padEnd(5, '_')) value = value * 85 + SYMBOLS.indexOf(char)
            if (value > 0xffffffffL) throw FrameException("encoding")
            List(chunk.length - 1) { index -> (value shr (24 - index * 8)).toByte() }
        }.toByteArray()
    }
    if (encodeBytes(bytes, alphabet) != text) throw FrameException("encoding")
    return bytes
}

/** Encode one frame, rejecting values that cannot be represented in the selected alphabet. */
fun encodeFrame(frame: Frame, alphabet: Alphabet = Alphabet.B64): String {
    require(frame.tag in 0..1295)
    require(frame.total in 1..MAX_FRAMES)
    require(frame.seq in 0 until frame.total)
    require(frame.body.size <= alphabet.frameBytes - HEADER_BYTES)
    val header =
        listOf(0x11.toByte(), (frame.tag shr 8).toByte(), frame.tag.toByte(), frame.seq.toByte(), frame.total.toByte())
    return encodeBytes((header + crc8(header + frame.body).toByte() + frame.body).toByteArray(), alphabet)
}

/** Decode either alphabet and report the first fault in protocol order. */
fun decodeFrame(input: String): Frame {
    val text = input.trim()
    val alphabet = if (text.startsWith('.')) Alphabet.Z85G else Alphabet.B64
    val bytes = decodeBytes(text, alphabet).map { it.toInt() and 255 }
    if (bytes.size !in HEADER_BYTES..alphabet.frameBytes) throw FrameException("length")
    if (bytes[0] shr 4 != FRAME_VERSION) throw FrameException("version")
    val body = bytes.drop(HEADER_BYTES).map { it.toByte() }
    if (crc8(bytes.take(5).map { it.toByte() } + body) != bytes[5]) throw FrameException("crc")
    if (bytes[0] and 15 != 1) throw FrameException("type")
    val tag = (bytes[1] shl 8) or bytes[2]
    if (tag >= 1296) throw FrameException("tag")
    if (bytes[4] == 0 || bytes[3] >= bytes[4]) throw FrameException("sequence")
    return Frame(tag, bytes[3], bytes[4], body)
}
