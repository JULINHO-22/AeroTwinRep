package com.twobit.aerotwin.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable

private val AeroTwinColorScheme = lightColorScheme(
    primary = AeroTwinColors.Primary,
    onPrimary = AeroTwinColors.TextOnPrimary,
    background = AeroTwinColors.Background,
    onBackground = AeroTwinColors.TextPrimary,
    surface = AeroTwinColors.Surface,
    onSurface = AeroTwinColors.TextPrimary,
    outline = AeroTwinColors.Border,
    error = AeroTwinColors.Critical,
)

@Composable
fun AeroTwinTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = AeroTwinColorScheme,
        typography = Typography(),
        content = content,
    )
}
