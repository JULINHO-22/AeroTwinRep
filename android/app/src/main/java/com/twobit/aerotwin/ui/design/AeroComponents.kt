package com.twobit.aerotwin.ui.design

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.IconButton
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.twobit.aerotwin.ui.theme.AeroTwinColors

enum class AeroStatusTone { SUCCESS, WARNING, CRITICAL, INFO, NEUTRAL }

private data class ToneColors(val foreground: Color, val background: Color)

private fun toneColors(tone: AeroStatusTone): ToneColors = when (tone) {
    AeroStatusTone.SUCCESS -> ToneColors(AeroTwinColors.Success, AeroTwinColors.SuccessSoft)
    AeroStatusTone.WARNING -> ToneColors(AeroTwinColors.Warning, AeroTwinColors.WarningSoft)
    AeroStatusTone.CRITICAL -> ToneColors(AeroTwinColors.Critical, AeroTwinColors.CriticalSoft)
    AeroStatusTone.INFO -> ToneColors(AeroTwinColors.Info, AeroTwinColors.InfoSoft)
    AeroStatusTone.NEUTRAL -> ToneColors(AeroTwinColors.Secondary, AeroTwinColors.SurfaceSubtle)
}

@Composable
fun AeroTopBar(
    eyebrow: String,
    title: String,
    detail: String? = null,
    showBack: Boolean = false,
    onBack: (() -> Unit)? = null,
) {
    Column {
        if (showBack && onBack != null) {
            IconButton(onClick = onBack, modifier = Modifier.height(36.dp)) {
                Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "Volver", tint = AeroTwinColors.TextPrimary)
            }
            Spacer(Modifier.height(4.dp))
        }
        Text(
            text = "AEROTWIN",
            color = AeroTwinColors.Primary,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.8.sp,
        )
        Spacer(Modifier.height(10.dp))
        Text(
            text = eyebrow.uppercase(),
            color = AeroTwinColors.TextSecondary,
            fontSize = 12.sp,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = 0.8.sp,
        )
        Spacer(Modifier.height(4.dp))
        Text(
            text = title,
            color = AeroTwinColors.TextPrimary,
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold,
            lineHeight = 34.sp,
        )
        detail?.let {
            Spacer(Modifier.height(6.dp))
            Text(text = it, color = AeroTwinColors.TextSecondary, lineHeight = 21.sp)
        }
    }
}

@Composable
fun ConnectionIndicator(
    connected: Boolean,
    label: String = if (connected) "AeroTwin Core conectado" else "AeroTwin Core sin conexión",
) {
    val color = if (connected) AeroTwinColors.Success else AeroTwinColors.Critical
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("●", color = color, fontSize = 14.sp)
        Spacer(Modifier.width(6.dp))
        Text(label, color = AeroTwinColors.TextSecondary, fontSize = 13.sp)
    }
}

@Composable
fun StatusBadge(label: String, tone: AeroStatusTone) {
    val colors = toneColors(tone)
    Text(
        text = label.uppercase(),
        color = colors.foreground,
        fontSize = 11.sp,
        fontWeight = FontWeight.Bold,
        letterSpacing = 0.5.sp,
        modifier = Modifier
            .background(colors.background, RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 5.dp),
    )
}

@Composable
fun SectionHeader(label: String, action: String? = null) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = label.uppercase(),
            color = AeroTwinColors.TextSecondary,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.9.sp,
        )
        action?.let { Text(it, color = AeroTwinColors.Primary, fontSize = 13.sp) }
    }
}

@Composable
fun AeroDivider() {
    HorizontalDivider(color = AeroTwinColors.Border, thickness = 1.dp)
}

@Composable
fun MetricTile(label: String, value: String, supporting: String? = null) {
    Column(
        modifier = Modifier
            .border(1.dp, AeroTwinColors.Border, RoundedCornerShape(8.dp))
            .padding(14.dp),
    ) {
        Text(label.uppercase(), color = AeroTwinColors.TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(7.dp))
        Text(value, color = AeroTwinColors.TextPrimary, fontSize = 24.sp, fontWeight = FontWeight.Bold)
        supporting?.let {
            Spacer(Modifier.height(2.dp))
            Text(it, color = AeroTwinColors.TextSecondary, fontSize = 12.sp)
        }
    }
}

@Composable
fun OperationalCode(label: String, code: String, emphasis: Color = AeroTwinColors.TextPrimary) {
    Column {
        Text(label.uppercase(), color = AeroTwinColors.TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 0.7.sp)
        Spacer(Modifier.height(5.dp))
        Text(
            code,
            color = emphasis,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            fontSize = 22.sp,
            letterSpacing = 0.2.sp,
        )
    }
}

@Composable
fun InspectionProgress(completed: Int, total: Int) {
    val progress = if (total == 0) 0f else completed.toFloat() / total.toFloat()
    Column {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("$completed de $total posiciones", color = AeroTwinColors.TextPrimary, fontWeight = FontWeight.SemiBold)
            Text("${(progress * 100).toInt()}%", color = AeroTwinColors.TextSecondary, fontFamily = FontFamily.Monospace)
        }
        Spacer(Modifier.height(9.dp))
        androidx.compose.material3.LinearProgressIndicator(
            progress = { progress },
            modifier = Modifier.fillMaxWidth().height(6.dp),
            color = AeroTwinColors.Primary,
            trackColor = AeroTwinColors.SurfaceSubtle,
        )
    }
}

@Composable
fun StateBanner(
    title: String,
    message: String,
    tone: AeroStatusTone,
    icon: ImageVector? = null,
) {
    val colors = toneColors(tone)
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(colors.background, RoundedCornerShape(8.dp))
            .padding(16.dp),
        verticalAlignment = Alignment.Top,
    ) {
        icon?.let {
            Icon(it, null, tint = colors.foreground)
            Spacer(Modifier.width(12.dp))
        }
        Column {
            Text(title, color = colors.foreground, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Text(message, color = AeroTwinColors.TextPrimary, lineHeight = 20.sp)
        }
    }
}

@Composable
fun ActionButton(
    text: String,
    onClick: () -> Unit,
    enabled: Boolean = true,
    icon: ImageVector? = null,
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier.fillMaxWidth().height(52.dp),
        shape = RoundedCornerShape(8.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = AeroTwinColors.Primary,
            contentColor = AeroTwinColors.TextOnPrimary,
            disabledContainerColor = AeroTwinColors.Border,
            disabledContentColor = AeroTwinColors.TextSecondary,
        ),
    ) {
        icon?.let {
            Icon(it, null)
            Spacer(Modifier.width(8.dp))
        }
        Text(text, fontWeight = FontWeight.Bold, letterSpacing = 0.3.sp)
    }
}

@Composable
fun SecondaryAction(
    text: String,
    onClick: () -> Unit,
    enabled: Boolean = true,
) {
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier.fillMaxWidth().height(48.dp),
        shape = RoundedCornerShape(8.dp),
        colors = ButtonDefaults.outlinedButtonColors(contentColor = AeroTwinColors.Primary),
        border = androidx.compose.foundation.BorderStroke(1.dp, AeroTwinColors.Border),
    ) {
        Text(text, fontWeight = FontWeight.SemiBold)
    }
}
