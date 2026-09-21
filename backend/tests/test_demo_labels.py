"""Printable QR labels keep the Sensor/Core payload contract intentionally small."""

from scripts.generate_rack_pallet_pairs import (
    OUTPUT,
    PAIRS,
    PALLET_PRODUCTS,
    SCENARIOS,
    location_payload,
    pallet_payload,
)


def test_rack_pair_labels_keep_loc_and_pal_qr_payloads() -> None:
    assert OUTPUT.as_posix().endswith(
        "artifacts/demo-labels/aerotwin-demo-rack-pallet-pairs.pdf"
    )
    for location, pallet in PAIRS:
        assert location_payload(location) == f"LOC:{location}"
        if pallet is not None:
            assert pallet_payload(pallet) == f"PAL:{pallet}"
            assert PALLET_PRODUCTS[pallet]


def test_printable_demo_keeps_correct_mismatch_unexpected_and_rescan_cases() -> None:
    scenarios = {(location, pallet): note for location, pallet, note in SCENARIOS}
    assert ("A-01-01", "PAL-001") in scenarios  # Correct
    assert ("A-01-02", "PAL-008") in scenarios  # Mismatch
    assert ("A-02-02", "PAL-011") in scenarios  # Unexpected pallet
    assert "ReScan" in scenarios[("B-01-01", "PAL-006")]
    assert {location for location, pallet in PAIRS if pallet is None} == {
        "A-02-02",
        "B-02-02",
    }
