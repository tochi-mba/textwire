package com.rextechnologies.textwire.protocol

import com.github.luben.zstd.Zstd
import com.github.luben.zstd.ZstdDictDecompress
import com.github.luben.zstd.ZstdException
import java.io.InputStream
import java.security.MessageDigest

/** The codec number of the shared dictionary, and its resource name inside the module. */
const val DICTIONARY_ID = 1
const val DICTIONARY_RESOURCE = "/textwire-v1.zdict"

/** The most text a compressed page may expand to (PROTOCOL.md section 4). */
const val MAX_TEXT_BYTES = 65536

/** Bytes that are not a zstd frame this dictionary can decode within the size limit. */
class CompressionException(message: String) : IllegalArgumentException(message)

/** The shared zstd dictionary, digested once for decompression. */
class ZstdDictionary(val bytes: ByteArray) {
    private val digested = ZstdDictDecompress(bytes)

    /** The dictionary's SHA-256 as lower-case hex, to compare with `protocol/vectors/ids.json`. */
    val sha256: String
        get() = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    /** The bytes a zstd frame holds, refusing frames without a size or above [maxSize]. */
    fun decompress(data: ByteArray, maxSize: Int = MAX_TEXT_BYTES): ByteArray {
        // Negative means an error or no declared size; both are refused (PROTOCOL.md section 4).
        val size = Zstd.getFrameContentSize(data)
        if (size < 0) throw CompressionException("not a zstd frame, or no declared size")
        if (size > maxSize) throw CompressionException("the frame declares $size bytes, more than $maxSize")
        val out = ByteArray(size.toInt())
        try {
            // Writes exactly the declared size or throws; a short write is reported as an error.
            Zstd.decompressFastDict(out, 0, data, 0, data.size, digested)
        } catch (error: ZstdException) {
            throw CompressionException("the frame is corrupt or needs another dictionary: ${error.message}")
        }
        return out
    }

    companion object {
        /** The dictionary packaged with the module (a copy of `protocol/dict/textwire-v1.zdict`). */
        fun packaged(resource: String = DICTIONARY_RESOURCE): ZstdDictionary {
            val stream: InputStream? = ZstdDictionary::class.java.getResourceAsStream(resource)
            if (stream == null) throw IllegalArgumentException("$resource is not on the classpath")
            val bytes = stream.readBytes()
            stream.close()
            return ZstdDictionary(bytes)
        }
    }
}
