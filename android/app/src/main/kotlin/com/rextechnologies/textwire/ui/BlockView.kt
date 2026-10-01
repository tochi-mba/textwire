package com.rextechnologies.textwire.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withLink
import androidx.compose.ui.unit.dp
import com.rextechnologies.textwire.core.Block
import com.rextechnologies.textwire.core.Span

/** One block of document text; chips are underlined and tappable. */
@Composable
fun BlockView(block: Block, follow: (Int) -> Unit) {
    when (block) {
        is Block.Title -> Text(
            block.text,
            style = MaterialTheme.typography.headlineSmall,
            modifier = Modifier.padding(bottom = 12.dp),
        )
        is Block.Heading -> Text(
            block.text,
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(vertical = 8.dp),
        )
        is Block.Paragraph -> Column(modifier = Modifier.padding(bottom = 12.dp)) {
            for (line in block.lines) SpanLine(line, follow)
        }
        is Block.Bullets -> Column(modifier = Modifier.padding(bottom = 12.dp)) {
            for (item in block.items) SpanLine(listOf(Span.Text("- ")) + item, follow)
        }
        is Block.Numbered -> Column(modifier = Modifier.padding(bottom = 12.dp)) {
            for ((number, item) in block.items) SpanLine(listOf(Span.Text("$number. ")) + item, follow)
        }
    }
}

@Composable
private fun SpanLine(spans: List<Span>, follow: (Int) -> Unit) {
    val chipStyle = TextLinkStyles(
        SpanStyle(
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.Bold,
            textDecoration = TextDecoration.Underline,
        ),
    )
    val text = buildAnnotatedString {
        for (span in spans) {
            when (span) {
                is Span.Text -> append(span.text)
                is Span.Chip -> withLink(
                    LinkAnnotation.Clickable(tag = span.number.toString(), styles = chipStyle) { link ->
                        follow((link as LinkAnnotation.Clickable).tag.toInt())
                    },
                ) {
                    append("[${span.number}]")
                }
            }
        }
    }
    Text(text = text, style = MaterialTheme.typography.bodyLarge)
}
