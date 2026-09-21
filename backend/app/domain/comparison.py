from app.models.enums import ComparisonResult, ObservedState


class InvalidObservationError(ValueError):
    """Raised when observed state and pallet information contradict each other."""


def compare_inventory(
    *,
    expected_pallet_id: int | None,
    observed_state: ObservedState,
    observed_pallet_id: int | None,
    empty_confirmed_by_operator: bool = False,
) -> ComparisonResult:
    if expected_pallet_id is not None and expected_pallet_id <= 0:
        raise InvalidObservationError("expected_pallet_id debe ser positivo")
    if observed_pallet_id is not None and observed_pallet_id <= 0:
        raise InvalidObservationError("observed_pallet_id debe ser positivo")

    if observed_state is ObservedState.UNRESOLVED:
        if observed_pallet_id is not None:
            raise InvalidObservationError(
                "Una observación UNRESOLVED no puede incluir observed_pallet_id"
            )
        return ComparisonResult.UNRESOLVED

    if observed_state is ObservedState.PALLET:
        if observed_pallet_id is None:
            raise InvalidObservationError(
                "Una observación PALLET requiere observed_pallet_id"
            )
        if expected_pallet_id is None:
            return ComparisonResult.UNEXPECTED_PALLET
        if expected_pallet_id == observed_pallet_id:
            return ComparisonResult.CORRECT
        return ComparisonResult.PALLET_MISMATCH

    if observed_state is ObservedState.EMPTY:
        if observed_pallet_id is not None:
            raise InvalidObservationError(
                "Una observación EMPTY no puede incluir observed_pallet_id"
            )
        if not empty_confirmed_by_operator:
            raise InvalidObservationError(
                "Una observación EMPTY debe estar confirmada por el operador"
            )
        if expected_pallet_id is None:
            return ComparisonResult.CORRECT_EMPTY
        return ComparisonResult.EXPECTED_PALLET_MISSING

    raise InvalidObservationError(f"ObservedState no soportado: {observed_state}")

