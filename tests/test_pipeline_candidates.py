from pathlib import Path

import pytest

from worker.pipeline.analysis import TimingAnalysis, analyze_timing
from worker.pipeline.amt import BasicPitchBaselineAdapter, NoteCandidate
from worker.pipeline.audio import NormalizedAudio


def make_timing_analysis(**overrides: float | int) -> TimingAnalysis:
    values: dict[str, float | int] = {
        "duration_seconds": 1.0,
        "tempo_bpm": 120.0,
        "seconds_per_beat": 0.5,
        "meter_numerator": 4,
        "meter_denominator": 4,
    }
    values.update(overrides)
    return TimingAnalysis(
        duration_seconds=float(values["duration_seconds"]),
        tempo_bpm=float(values["tempo_bpm"]),
        seconds_per_beat=float(values["seconds_per_beat"]),
        meter_numerator=int(values["meter_numerator"]),
        meter_denominator=int(values["meter_denominator"]),
    )


def make_note_candidate(**overrides: float | int | str) -> NoteCandidate:
    values: dict[str, float | int | str] = {
        "midi": 60,
        "name": "C4",
        "start_seconds": 0.0,
        "end_seconds": 0.5,
        "confidence": 0.35,
    }
    values.update(overrides)
    return NoteCandidate(
        midi=int(values["midi"]),
        name=str(values["name"]),
        start_seconds=float(values["start_seconds"]),
        end_seconds=float(values["end_seconds"]),
        confidence=float(values["confidence"]),
    )


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    [
        ("duration_seconds", -0.1, "duration_seconds must be non-negative"),
        ("tempo_bpm", 0.0, "tempo_bpm must be greater than 0"),
        ("seconds_per_beat", 0.0, "seconds_per_beat must be greater than 0"),
        ("meter_numerator", 0, "meter_numerator must be greater than 0"),
        ("meter_denominator", 0, "meter_denominator must be greater than 0"),
    ],
)
def test_timing_analysis_rejects_invalid_values(
    field_name: str,
    invalid_value: float | int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        make_timing_analysis(**{field_name: invalid_value})


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    [
        ("midi", -1, "midi must be between 0 and 127"),
        ("midi", 128, "midi must be between 0 and 127"),
        ("name", " ", "name must not be empty"),
        ("start_seconds", -0.1, "start_seconds must be non-negative"),
        ("end_seconds", 0.0, "end_seconds must be greater than start_seconds"),
        ("confidence", -0.1, "confidence must be between 0 and 1"),
        ("confidence", 1.1, "confidence must be between 0 and 1"),
    ],
)
def test_note_candidate_rejects_invalid_values(
    field_name: str,
    invalid_value: float | int | str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        make_note_candidate(**{field_name: invalid_value})


def test_basic_pitch_baseline_adapter_produces_valid_candidates() -> None:
    audio = NormalizedAudio(
        path=Path("normalized.wav"),
        duration_seconds=1.0,
        sample_rate=44_100,
        channel_count=1,
    )
    analysis = analyze_timing(audio)

    candidates = BasicPitchBaselineAdapter().transcribe(audio, analysis)

    assert candidates
    assert all(0 <= candidate.midi <= 127 for candidate in candidates)
    assert all(candidate.end_seconds > candidate.start_seconds for candidate in candidates)
    assert all(0 <= candidate.confidence <= 1 for candidate in candidates)
