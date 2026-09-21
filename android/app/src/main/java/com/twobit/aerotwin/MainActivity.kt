package com.twobit.aerotwin

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import com.twobit.aerotwin.ui.app.AeroTwinApp
import com.twobit.aerotwin.ui.app.AeroTwinViewModel
import com.twobit.aerotwin.ui.theme.AeroTwinTheme

class MainActivity : ComponentActivity() {
    private val appViewModel: AeroTwinViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            AeroTwinTheme {
                AeroTwinApp(viewModel = appViewModel)
            }
        }
    }
}
