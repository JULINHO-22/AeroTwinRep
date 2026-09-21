import pytest

from app.domain.comparison import InvalidObservationError, compare_inventory
from app.models.enums import ComparisonResult, ObservedState


@pytest.mark.parametrize(
    ("expected", "state", "observed", "empty_confirmed", "result"),
    [
        (1, ObservedState.PALLET, 1, False, ComparisonResult.CORRECT),
        (1, ObservedState.PALLET, 2, False, ComparisonResult.PALLET_MISMATCH),
        (
            1,
            ObservedState.EMPTY,
            None,
            True,
            ComparisonResult.EXPECTED_PALLET_MISSING,
        ),
        (
            None,
            ObservedState.PALLET,
            2,
            False,
            ComparisonResult.UNEXPECTED_PALLET,
        ),
        (
            None,
            ObservedState.EMPTY,
            None,
            True,
            ComparisonResult.CORRECT_EMPTY,
        ),
        (
            1,
            ObservedState.UNRESOLVED,
            None,
            False,
            ComparisonResult.UNRESOLVED,
        ),
    ],
)
def test_comparison_matrix(expected, state, observed, empty_confirmed, result) -> None:
    assert compare_inventory(
        expected_pallet_id=expected,
        observed_state=state,
        observed_pallet_id=observed,
        empty_confirmed_by_operator=empty_confirmed,
    ) is result


@pytest.mark.parametrize(
    ("state", "observed", "empty_confirmed"),
    [
        (ObservedState.PALLET, None, False),
        (ObservedState.EMPTY, 2, True),
        (ObservedState.EMPTY, None, False),
        (ObservedState.UNRESOLVED, 2, False),
    ],
)
def test_incoherent_observation_raises(state, observed, empty_confirmed) -> None:
    with pytest.raises(InvalidObservationError):
        compare_inventory(
            expected_pallet_id=1,
            observed_state=state,
            observed_pallet_id=observed,
            empty_confirmed_by_operator=empty_confirmed,
        )

