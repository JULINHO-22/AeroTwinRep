package com.twobit.aerotwin.sensor;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.assertTrue;
import com.twobit.aerotwin.ui.sensor.CameraFrameScannerKt;
import com.twobit.aerotwin.ui.sensor.CameraBarcodeDetection;
import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.vision.barcode.BarcodeScanning;
import com.google.mlkit.vision.common.InputImage;
import java.io.InputStream;
import java.util.List;
import java.util.concurrent.TimeUnit;

public class QrPhotographTest {
    private Bitmap asset(String name) throws Exception {
        try (InputStream stream = InstrumentationRegistry.getInstrumentation().getContext().getAssets().open(name)) {
            return BitmapFactory.decodeStream(stream);
        }
    }

    @Test public void testActualUserPhotographDecodesOffline() throws Exception {
        List<CameraBarcodeDetection> codes = CameraFrameScannerKt.decodeQrBitmap(asset("phone-qr.jpg"));
        assertTrue("The QR in the user's camera screenshot must decode", codes.stream()
            .anyMatch(code -> code.getRawValue().equals("LOC:A-01-01")));
    }

    @Test public void testPalletLabelDecodesOffline() throws Exception {
        List<CameraBarcodeDetection> codes = CameraFrameScannerKt.decodeQrBitmap(asset("pallet.png"));
        assertTrue(codes.stream().anyMatch(code -> code.getRawValue().equals("PAL:PAL-001")));
    }

    @Test public void testPhotographWithBundledMlKit() throws Exception {
        com.google.mlkit.vision.barcode.BarcodeScanner scanner = BarcodeScanning.getClient();
        try {
            assertTrue(Tasks.await(scanner.process(InputImage.fromBitmap(asset("phone-qr.jpg"), 0)), 15, TimeUnit.SECONDS)
                .stream().anyMatch(code -> "LOC:A-01-01".equals(code.getRawValue())));
        } finally { scanner.close(); }
    }
}
