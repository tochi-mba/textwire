package com.rextechnologies.textwire.protocol

/** What a request asks for (PROTOCOL.md section 6). */
enum class Verb(val letter: String) {
    GET("g"),
    SEARCH("s"),
    PAGE("p"),
    LINK("l"),
    RESEND("r"),
    STATUS("?"),
    HELP("h"),
}

/** Verbs whose replies are paged, and so accept a size. */
val SIZED_VERBS: Set<Verb> = setOf(Verb.GET, Verb.SEARCH, Verb.PAGE, Verb.LINK)

/**
 * One request the phone sends. Which optional fields are set depends on the verb; the
 * constructor checks the combinations the grammar allows so a bad request cannot be built.
 */
data class Request(
    val verb: Verb,
    val tag: Int? = null,
    val size: Int? = null,
    val plain: Boolean = false,
    val url: String? = null,
    val words: String? = null,
    val ref: Int? = null,
    val number: Int? = null,
    val seqs: List<Int> = emptyList(),
) {
    init {
        if (tag != null) check(isTag(tag), "tag $tag is outside 0-${TAG_COUNT - 1}")
        if (size != null) {
            check(verb in SIZED_VERBS, "a size is not allowed on ${verb.letter}")
            check(size in 1..255, "size must be 1-255")
        }
        check(!plain || verb != Verb.RESEND, "plain is not allowed on r")
        when (verb) {
            Verb.GET -> check(!url.isNullOrEmpty(), "g needs a url")
            Verb.SEARCH -> check(!words.isNullOrEmpty(), "s needs words")
            Verb.PAGE, Verb.LINK -> {
                check(ref != null && isTag(ref), "${verb.letter} needs a referenced tag")
                check(number != null && number in 1..255, "number must be 1-255")
            }
            Verb.RESEND -> {
                check(ref != null && isTag(ref), "r needs a referenced tag")
                check(seqs.isNotEmpty() && seqs.all { it in 0 until MAX_FRAMES }, "bad frame list")
            }
            Verb.STATUS, Verb.HELP -> Unit
        }
    }

    private fun isTag(value: Int): Boolean = value in 0 until TAG_COUNT

    private fun check(condition: Boolean, message: String) {
        if (!condition) throw IllegalArgumentException(message)
    }
}

/** The shortest form of a set of frame numbers: `[3, 5, 6, 7]` becomes `"3,5-7"`. */
fun formatSeqs(seqs: Collection<Int>): String {
    if (seqs.isEmpty()) throw IllegalArgumentException("no frame numbers")
    val ordered = seqs.toSortedSet().toIntArray()
    val parts = mutableListOf<String>()
    var start = ordered[0]
    var previous = start
    for (index in 1 until ordered.size) {
        val seq = ordered[index]
        if (seq != previous + 1) {
            parts.add(run(start, previous))
            start = seq
        }
        previous = seq
    }
    parts.add(run(start, previous))
    return parts.joinToString(",")
}

private fun run(first: Int, last: Int): String = if (first == last) "$first" else "$first-$last"

/** The canonical text of [request]: what the phone sends (PROTOCOL.md section 6.3). */
fun formatRequest(request: Request): String {
    val head = buildString {
        append(request.verb.letter)
        request.size?.let { append(it) }
        if (request.plain) append('!')
    }
    val words = mutableListOf<String>()
    request.tag?.let { words.add(encodeTag(it)) }
    words.add(head)
    when (request.verb) {
        Verb.GET -> words.add(request.url!!)
        Verb.SEARCH -> words.add(request.words!!)
        Verb.PAGE, Verb.LINK -> {
            words.add(encodeTag(request.ref!!))
            words.add(request.number!!.toString())
        }
        Verb.RESEND -> {
            words.add(encodeTag(request.ref!!))
            words.add(formatSeqs(request.seqs))
        }
        Verb.STATUS, Verb.HELP -> Unit
    }
    return words.joinToString(" ")
}
