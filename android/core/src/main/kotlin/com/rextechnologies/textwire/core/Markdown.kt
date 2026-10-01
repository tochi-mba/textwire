package com.rextechnologies.textwire.core

/** A run of text or a link chip inside a block (PROTOCOL.md section 5). */
sealed interface Span {
    data class Text(val text: String) : Span

    /** `[n]`: link number [number] of the document. */
    data class Chip(val number: Int) : Span
}

/** One block of document text. */
sealed interface Block {
    data class Title(val text: String) : Block

    data class Heading(val text: String) : Block

    data class Paragraph(val lines: List<List<Span>>) : Block

    data class Bullets(val items: List<List<Span>>) : Block

    data class Numbered(val items: List<Pair<Int, List<Span>>>) : Block
}

private val CHIP = Regex("""\[(\d{1,2})]""")
private val NUMBERED = Regex("""^(\d{1,3})\. (.*)$""")
private const val MAX_CHIP = 60

/** Split one line into text and chips. */
fun spans(line: String): List<Span> {
    val out = mutableListOf<Span>()
    var at = 0
    for (match in CHIP.findAll(line)) {
        val number = match.groupValues[1].toInt()
        if (number !in 1..MAX_CHIP) continue
        if (match.range.first > at) out.add(Span.Text(line.substring(at, match.range.first)))
        out.add(Span.Chip(number))
        at = match.range.last + 1
    }
    if (at < line.length) out.add(Span.Text(line.substring(at)))
    return out
}

/** Parse document text into blocks. Anything that is not a recognised shape is a paragraph. */
fun parseDocument(text: String): List<Block> {
    val blocks = mutableListOf<Block>()
    val chunks = text.replace("\r\n", "\n").split(Regex("\n{2,}")).map { it.trim('\n') }.filter { it.isNotBlank() }
    for ((index, chunk) in chunks.withIndex()) {
        val lines = chunk.lines()
        val first = lines.first()
        blocks.add(
            when {
                index == 0 && first.startsWith("# ") && lines.size == 1 -> Block.Title(first.removePrefix("# ").trim())
                first.startsWith("## ") && lines.size == 1 -> Block.Heading(first.removePrefix("## ").trim())
                first.startsWith("- ") -> Block.Bullets(items(lines, "- ") { it.removePrefix("- ") })
                NUMBERED.matches(first) -> Block.Numbered(numberedItems(lines))
                else -> Block.Paragraph(lines.map(::spans))
            },
        )
    }
    return blocks
}

private fun items(lines: List<String>, marker: String, strip: (String) -> String): List<List<Span>> {
    // The first line carries the marker: that is how the block was recognised.
    val collected = mutableListOf(strip(lines.first()))
    for (line in lines.drop(1)) {
        if (line.startsWith(marker)) collected.add(strip(line)) else collected[collected.lastIndex] += " " + line.trim()
    }
    return collected.map(::spans)
}

private fun numberedItems(lines: List<String>): List<Pair<Int, List<Span>>> {
    val collected = mutableListOf<Pair<Int, String>>()
    for (line in lines) {
        val match = NUMBERED.matchEntire(line)
        if (match != null) {
            collected.add(match.groupValues[1].toInt() to match.groupValues[2])
        } else {
            // The first line always matches; a later one that does not continues the item above.
            val (number, text) = collected.last()
            collected[collected.lastIndex] = number to (text + " " + line.trim())
        }
    }
    return collected.map { (number, text) -> number to spans(text) }
}
