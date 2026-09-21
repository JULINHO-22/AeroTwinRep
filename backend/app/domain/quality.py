from app.models.enums import ReadingStatus


def evaluate_reading_quality(
    *,
    quality_score: int,
    attempt_number: int,
    quality_threshold: int,
    max_reading_attempts: int,
) -> ReadingStatus:
    if not 0 <= quality_score <= 100:
        raise ValueError("quality_score debe estar entre 0 y 100")
    if not 0 <= quality_threshold <= 100:
        raise ValueError("quality_threshold debe estar entre 0 y 100")
    if max_reading_attempts < 1:
        raise ValueError("max_reading_attempts debe ser al menos 1")
    if not 1 <= attempt_number <= max_reading_attempts:
        raise ValueError(
            "attempt_number debe estar entre 1 y max_reading_attempts"
        )

    if quality_score >= quality_threshold:
        return ReadingStatus.ACCEPTED
    if attempt_number < max_reading_attempts:
        return ReadingStatus.RESCAN_REQUIRED
    return ReadingStatus.HUMAN_REVIEW_REQUIRED

