from datetime import datetime
from uuid import UUID, uuid4

from shared.schemas.score import DraftScore
from worker.pipeline.analysis import TimingAnalysis, build_beat_points
from worker.pipeline.amt import NoteCandidate


MAIN_TRACK_ID = "track-main"
CHORD_TRACK_ID = "track-chords"


def build_draft_score(
    *,
    project_id: UUID,
    analysis: TimingAnalysis,
    note_candidates: list[NoteCandidate],
    created_at: datetime,
) -> DraftScore:
    draft_score_id = uuid4()
    notes = [
        _build_note_payload(index=index, candidate=candidate, analysis=analysis)
        for index, candidate in enumerate(note_candidates, start=1)
    ]
    payload = {
        "id": draft_score_id,
        "project_id": project_id,
        "version": 1,
        "beat_grid": {
            "tempo_bpm": analysis.tempo_bpm,
            "meter_numerator": analysis.meter_numerator,
            "meter_denominator": analysis.meter_denominator,
            "beats": build_beat_points(analysis),
            "confidence": {
                "overall": 0.5,
                "onset": 0.5,
                "duration": 0.45,
            },
        },
        "tracks": [
            {
                "id": MAIN_TRACK_ID,
                "kind": "main_melody",
                "name": "Main Melody",
            },
            {
                "id": CHORD_TRACK_ID,
                "kind": "chords",
                "name": "Chord Candidates",
            },
        ],
        "notes": notes,
        "chords": [],
        "uncertainty_markers": _build_uncertainty_markers(note_candidates, analysis),
        "created_at": created_at,
        "updated_at": created_at,
    }
    return DraftScore.model_validate(payload)


def _build_note_payload(
    *,
    index: int,
    candidate: NoteCandidate,
    analysis: TimingAnalysis,
) -> dict[str, object]:
    duration_seconds = candidate.end_seconds - candidate.start_seconds
    start_beat = candidate.start_seconds / analysis.seconds_per_beat
    duration_beats = duration_seconds / analysis.seconds_per_beat
    return {
        "id": f"note-{index}",
        "track_id": MAIN_TRACK_ID,
        "pitch": {
            "midi": candidate.midi,
            "name": candidate.name,
        },
        "audio_start_seconds": candidate.start_seconds,
        "audio_end_seconds": candidate.end_seconds,
        "start_beat": round(start_beat, 6),
        "duration_beats": round(duration_beats, 6),
        "source": "model",
        "confidence": {
            "overall": candidate.confidence,
            "pitch": candidate.confidence,
            "onset": 0.5,
            "duration": 0.45,
        },
        "notation_hints": {},
    }


def _build_uncertainty_markers(
    note_candidates: list[NoteCandidate],
    analysis: TimingAnalysis,
) -> list[dict[str, object]]:
    if note_candidates:
        first_candidate = note_candidates[0]
        start_beat = first_candidate.start_seconds / analysis.seconds_per_beat
        duration_beats = (
            first_candidate.end_seconds - first_candidate.start_seconds
        ) / analysis.seconds_per_beat
        end_beat = start_beat + duration_beats
        return [
            {
                "id": "uncertain-1",
                "type": "pitch_uncertain",
                "message": "Baseline AMT output needs user review.",
                "audio_range": {
                    "start_seconds": first_candidate.start_seconds,
                    "end_seconds": first_candidate.end_seconds,
                },
                "beat_range": {
                    "start_beat": round(start_beat, 6),
                    "end_beat": round(end_beat, 6),
                },
                "note_ids": ["note-1"],
                "chord_event_ids": [],
                "confidence": {
                    "overall": 0.35,
                    "pitch": 0.35,
                },
            },
        ]

    return [
        {
            "id": "uncertain-1",
            "type": "pitch_uncertain",
            "message": "Baseline AMT did not produce note candidates.",
            "audio_range": {
                "start_seconds": 0.0,
                "end_seconds": analysis.duration_seconds,
            },
            "beat_range": {
                "start_beat": 0.0,
                "end_beat": round(analysis.duration_seconds / analysis.seconds_per_beat, 6),
            },
            "note_ids": [],
            "chord_event_ids": [],
            "confidence": {
                "overall": 0.2,
                "pitch": 0.2,
            },
        },
    ]
