package com.rextechnologies.textwire.protocol

/** Two base-36 characters naming one response (PROTOCOL.md section 3). */
private const val TAG_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"

/** How many tags exist: `00` to `zz`. */
const val TAG_COUNT = 1296

/** The first tag the server allocates (`z0`); a phone allocates everything below it. */
const val SERVER_TAG_FIRST = 1260

/** `367` becomes `"a7"`. */
fun encodeTag(tag: Int): String {
    require(tag in 0 until TAG_COUNT) { "tag $tag is outside 0-${TAG_COUNT - 1}" }
    return "${TAG_ALPHABET[tag / 36]}${TAG_ALPHABET[tag % 36]}"
}

/** `"a7"` (either case) becomes `367`, or null when the text is not a tag. */
fun decodeTag(text: String): Int? {
    if (text.length != 2) return null
    val high = TAG_ALPHABET.indexOf(text[0].lowercaseChar())
    val low = TAG_ALPHABET.indexOf(text[1].lowercaseChar())
    if (high < 0 || low < 0) return null
    return high * 36 + low
}
