package com.rextechnologies.textwire.core

import kotlin.test.Test
import kotlin.test.assertEquals

class MarkdownTest {
    private fun t(text: String) = Span.Text(text)

    @Test
    fun `a page parses into its blocks`() {
        val text = """
            # Village gets its first text-only library

            Residents of Dunmore can borrow the news by text, said Morag Keir[1], who
            started the project.

            ## How it works

            - Search the web by texting a few words
            - Follow a link[2]
              continued line
            - Last

            1. A search usually takes four messages.
            2. A news story usually takes twelve.
            continued

            "It is slow, but it is ours."
        """.trimIndent()
        assertEquals(
            listOf(
                Block.Title("Village gets its first text-only library"),
                Block.Paragraph(
                    listOf(
                        listOf(
                            t("Residents of Dunmore can borrow the news by text, said Morag Keir"),
                            Span.Chip(1),
                            t(", who"),
                        ),
                        listOf(t("started the project.")),
                    ),
                ),
                Block.Heading("How it works"),
                Block.Bullets(
                    listOf(
                        listOf(t("Search the web by texting a few words")),
                        listOf(t("Follow a link"), Span.Chip(2), t(" continued line")),
                        listOf(t("Last")),
                    ),
                ),
                Block.Numbered(
                    listOf(
                        1 to listOf(t("A search usually takes four messages.")),
                        2 to listOf(t("A news story usually takes twelve. continued")),
                    ),
                ),
                Block.Paragraph(listOf(listOf(t("\"It is slow, but it is ours.\"")))),
            ),
            parseDocument(text),
        )
    }

    @Test
    fun `chips are only one to sixty and only in brackets`() {
        assertEquals(
            listOf(t("a"), Span.Chip(60), t(" [61] [0] b"), Span.Chip(7), t("c")),
            spans("a[60] [61] [0] b[7]c"),
        )
        assertEquals(listOf(Span.Chip(3)), spans("[3]"))
        assertEquals(emptyList(), spans(""))
        assertEquals(listOf(t("plain")), spans("plain"))
    }

    @Test
    fun `a title only counts as the first block and only alone`() {
        assertEquals(
            listOf(Block.Paragraph(listOf(listOf(t("# Not first"))))),
            parseDocument("x\n\n# Not first").drop(1),
        )
        assertEquals(
            listOf(Block.Paragraph(listOf(listOf(t("# Two")), listOf(t("lines"))))),
            parseDocument("# Two\nlines"),
        )
        assertEquals(
            listOf(Block.Paragraph(listOf(listOf(t("## Two")), listOf(t("lines"))))),
            parseDocument("## Two\nlines"),
        )
    }

    @Test
    fun `blank text has no blocks and windows line endings are fine`() {
        assertEquals(emptyList(), parseDocument("  \n\n "))
        assertEquals(listOf(Block.Title("T"), Block.Paragraph(listOf(listOf(t("p"))))), parseDocument("# T\r\n\r\np"))
    }

    @Test
    fun `a list that starts without its marker keeps its first line`() {
        assertEquals(
            listOf(Block.Numbered(listOf(1 to listOf(t("one")), 2 to listOf(t("two"))))),
            parseDocument("1. one\n2. two"),
        )
        assertEquals(listOf(Block.Bullets(listOf(listOf(t("a b"))))), parseDocument("- a\n  b"))
    }
}
