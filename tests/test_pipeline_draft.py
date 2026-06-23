from uuid import uuid4

from server.schemas.assets import utc_now
from worker.pipeline.analysis import TimingAnalysis
from worker.pipeline.draft import build_draft_score


def test_build_draft_score_adds_beat_range_to_empty_candidate_marker() -> None:
    analysis = TimingAnalysis(
        duration_seconds=1.0,
        tempo_bpm=120.0,
        seconds_per_beat=0.5,
        meter_numerator=4,
        meter_denominator=4,
    )

    draft_score = build_draft_score(
        project_id=uuid4(),
        analysis=analysis,
        note_candidates=[],
        created_at=utc_now(),
    )

    marker = draft_score.uncertainty_markers[0]
    assert marker.beat_range is not None
    assert marker.beat_range.start_beat == 0.0
    assert marker.beat_range.end_beat == 2.0
