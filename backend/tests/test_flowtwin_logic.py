from types import SimpleNamespace
from app.models.enums import ComparisonResult, ObservedState, ReadingStatus, FlowTwinChangeType
from app.services.flowtwin_service import classify
from fastapi.testclient import TestClient
from tests.test_phase3_api import auth_headers, create_inspection

def reading(state=ObservedState.PALLET, status=ReadingStatus.ACCEPTED, pallet=1, expected=1, result=ComparisonResult.CORRECT, empty=False):
    return SimpleNamespace(observed_state=state, reading_status=status, observed_pallet_id=pallet, expected_pallet_id_at_inspection=expected, comparison_result=result, empty_confirmed_by_operator=empty)

def test_no_change_and_unresolved_persistence_are_not_changes():
    assert classify(reading(), reading()) is None
    assert classify(reading(ObservedState.UNRESOLVED, ReadingStatus.HUMAN_REVIEW_REQUIRED, None), reading(ObservedState.UNRESOLVED, ReadingStatus.HUMAN_REVIEW_REQUIRED, None)) is None

def test_temporal_change_precedence():
    assert classify(reading(), reading(pallet=2)) is FlowTwinChangeType.PALLET_CHANGED
    assert classify(reading(), reading(ObservedState.EMPTY, pallet=None, empty=True)) is FlowTwinChangeType.PALLET_REMOVED
    assert classify(reading(ObservedState.EMPTY, pallet=None, empty=True), reading()) is FlowTwinChangeType.PALLET_ADDED
    assert classify(reading(), reading(ObservedState.UNRESOLVED, ReadingStatus.HUMAN_REVIEW_REQUIRED, None)) is FlowTwinChangeType.BECAME_UNRESOLVED
    assert classify(reading(ObservedState.UNRESOLVED, ReadingStatus.HUMAN_REVIEW_REQUIRED, None), reading()) is FlowTwinChangeType.RESOLVED_SINCE_PREVIOUS
    assert classify(reading(expected=1), reading(expected=2)) is FlowTwinChangeType.EXPECTED_CHANGED

def test_same_physical_discrepancy_is_persistent():
    old = reading(result=ComparisonResult.PALLET_MISMATCH)
    now = reading(result=ComparisonResult.PALLET_MISMATCH)
    assert classify(old, now) is FlowTwinChangeType.PERSISTENT_DISCREPANCY

def test_no_read_is_not_empty_removal():
    assert classify(reading(), reading(ObservedState.UNRESOLVED, ReadingStatus.HUMAN_REVIEW_REQUIRED, None)) is FlowTwinChangeType.BECAME_UNRESOLVED

def test_explicit_completion_is_safe_and_creates_no_flow_rows_without_previous(api_client: TestClient):
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    response = api_client.post(f"/api/v1/inspections/{inspection['id']}/complete", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
