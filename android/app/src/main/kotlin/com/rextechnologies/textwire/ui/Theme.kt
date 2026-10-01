package com.rextechnologies.textwire.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// The REX ink/signal palette, shared with the site and the server's dashboard. Dark by design:
// pages are read for minutes at a time, often at night, on an OLED screen.
private val Ink = Color(0xFF080A09)
private val Panel = Color(0xFF111512)
private val Raised = Color(0xFF181E19)
private val Line = Color(0xFF29302A)
private val TextColor = Color(0xFFF2F5EE)
private val Muted = Color(0xFF858D83)
private val Signal = Color(0xFFD7FF3F)
private val Live = Color(0xFFFF774D)

private val RexColors = darkColorScheme(
    primary = Signal,
    onPrimary = Ink,
    primaryContainer = Color(0xFF2A3310),
    onPrimaryContainer = Color(0xFFECFFA6),
    secondary = TextColor,
    onSecondary = Ink,
    secondaryContainer = Line,
    onSecondaryContainer = TextColor,
    tertiary = Live,
    onTertiary = Ink,
    background = Ink,
    onBackground = TextColor,
    surface = Ink,
    onSurface = TextColor,
    surfaceVariant = Raised,
    onSurfaceVariant = Muted,
    surfaceContainerLowest = Ink,
    surfaceContainerLow = Color(0xFF0D100E),
    surfaceContainer = Panel,
    surfaceContainerHigh = Raised,
    surfaceContainerHighest = Raised,
    inverseSurface = TextColor,
    inverseOnSurface = Ink,
    inversePrimary = Color(0xFF4F6200),
    outline = Color(0xFF5B645A),
    outlineVariant = Line,
    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
)

/** Reading sizes: pages are read for minutes at a time, so body text is a touch larger than default. */
private val ReadingTypography = Typography(
    headlineSmall = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 24.sp, lineHeight = 32.sp),
    titleMedium = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 18.sp, lineHeight = 26.sp),
    bodyLarge = TextStyle(fontFamily = FontFamily.Default, fontSize = 17.sp, lineHeight = 27.sp),
    bodyMedium = TextStyle(fontSize = 15.sp, lineHeight = 22.sp),
    bodySmall = TextStyle(fontSize = 13.sp, lineHeight = 18.sp),
    labelLarge = TextStyle(fontWeight = FontWeight.Medium, fontSize = 14.sp, lineHeight = 20.sp),
)

/** The app's theme: REX ink and signal, the same on every phone. */
@Composable
fun TextwireTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = RexColors, typography = ReadingTypography, content = content)
}
