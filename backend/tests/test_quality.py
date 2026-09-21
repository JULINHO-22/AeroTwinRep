import pytest

from app.domain.quality import evaluate_reading_quality
from app.models.enums import ReadingStatus


@pytest.mark.parametrize(
    ("score", "attempt", "expected"),
    [
        (42, 1, ReadingStatus.RESCAN_REQUIRED),
        (94, 1, ReadingStatus.ACCEPTED),
        (94, 2, ReadingStatus.ACCEPTED),
        (40, 2, ReadingStatus.HUMAN_REVIEW_REQUIRED),
        (85, 1, ReadingStatus.ACCEPTED),
    ],
)
def test_quality_policy(score, attempt, expected) -> None:
    assert evaluate_reading_quality(
        quality_score=score,
        attempt_number=attempt,
        quality_threshold=85,
        max_reading_attempts=2,
    ) is expected


@pytest.mark.parametrize("score", [-1, 101])
def test_quality_score_must_be_in_range(score) -> None:
    with pytest.raises(ValueError):
        evaluate_reading_quality(
            quality_score=score,
            attempt_number=1,
            quality_threshold=85,
            max_reading_attempts=2,
        )


def test_attempt_cannot_exceed_total_attempt_limit() -> None:
    with pytest.raises(ValueError):
        evaluate_reading_quality(
            quality_score=90,
            attempt_number=3,
            quality_threshold=85,
            max_reading_attempts=2,
        )

