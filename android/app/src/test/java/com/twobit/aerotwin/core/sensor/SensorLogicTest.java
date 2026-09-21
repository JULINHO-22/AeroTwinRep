package com.twobit.aerotwin.core.sensor;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

public class SensorLogicTest {
    @Test public void parsesOnlyExplicitQrFormats() {
        SensorQrCode location = SensorLogicKt.parseSensorQr("LOC:A-01-01");
        SensorQrCode pallet = SensorLogicKt.parseSensorQr("PAL:PAL-008");
        assertTrue(location instanceof SensorQrCode.Location);
        assertTrue(pallet instanceof SensorQrCode.Pallet);
        assertNull(SensorLogicKt.parseSensorQr("A-01-01"));
    }

    @Test public void requiresThreeFramesAndScoresQuality() {
        StabilityTracker tracker = new StabilityTracker(3, 2);
        for (int index = 0; index < 3; index++) tracker.observe("PAL-001");
        assertTrue(tracker.isStable("PAL-001"));
        CaptureQuality quality = SensorLogicKt.calculateCaptureQuality(
            3, new SensorBox(0f, 0f, 320f, 320f), 1000, 1000, .55f
        );
        assertEquals(100, quality.getScore());
    }

    @Test public void marksSmallAndDarkCodesAsLowQuality() {
        CaptureQuality quality = SensorLogicKt.calculateCaptureQuality(
            1, new SensorBox(0f, 0f, 20f, 20f), 1000, 1000, .20f
        );
        assertTrue(quality.getScore() <= 50);
        assertTrue(quality.getReasons().contains("TOO_FAR"));
        assertTrue(quality.getReasons().contains("LOW_BRIGHTNESS"));
    }

    @Test public void stabilityTrackerResistsIntermittentMisses() {
        StabilityTracker tracker = new StabilityTracker(3, 2); // graceFrames = 2
        
        // 1. Reaching stability
        tracker.observe("PAL-001");
        tracker.observe("PAL-001");
        tracker.observe("PAL-001");
        assertTrue(tracker.isStable("PAL-001"));
        
        // 2. Missing one frame (within grace period)
        tracker.miss();
        assertTrue("Should still be stable after 1 miss", tracker.isStable("PAL-001"));
        assertEquals(1, tracker.currentMissed());
        
        // 3. Missing second frame (within grace period)
        tracker.miss();
        assertTrue("Should still be stable after 2 misses", tracker.isStable("PAL-001"));
        assertEquals(2, tracker.currentMissed());
        
        // 4. Recovery
        tracker.observe("PAL-001");
        assertEquals("Misses should reset on recovery", 0, tracker.currentMissed());
        assertTrue("Should maintain stability", tracker.isStable("PAL-001"));
        
        // 5. Hard failure (exceeding grace period)
        tracker.miss();
        tracker.miss();
        tracker.miss(); // Third miss exceeds grace period (2)
        assertEquals("Tracker should completely reset", 0, tracker.currentFrames());
        assertTrue("Should no longer be stable", !tracker.isStable("PAL-001"));
    }
}
