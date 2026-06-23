from dataclasses import dataclass
from math import ceil
from typing import Protocol

from worker.pipeline.analysis import TimingAnalysis
from worker.pipeline.audio import NormalizedAudio


PITCH_CYCLE = (
    (60, "C4"),
    (64, "E4"),
    (67, "G4"),
    (72, "C5"),
)


@dataclass(frozen=True, kw_only=True)
class NoteCandidate:
    midi: int
    name: str
    start_seconds: float
    end_seconds: float
    confidence: float


class AmtAdapter(Protocol):
    def transcribe(
        self, audio: NormalizedAudio, analysis: TimingAnalysis
    ) -> list[NoteCandidate]: ...


class BasicPitchBaselineAdapter:
    """Deterministic stand-in behind the Basic Pitch adapter boundary."""

    def transcribe(self, audio: NormalizedAudio, analysis: TimingAnalysis) -> list[NoteCandidate]:
        note_count = max(1, min(8, ceil(audio.duration_seconds / analysis.seconds_per_beat)))
        candidates: list[NoteCandidate] = []
        for index in range(note_count):
            start_seconds = index * analysis.seconds_per_beat
            if start_seconds >= audio.duration_seconds:
                break
            end_seconds = min(
                start_seconds + (analysis.seconds_per_beat * 0.9), audio.duration_seconds
            )
            if end_seconds <= start_seconds:
                continue
            midi, name = PITCH_CYCLE[index % len(PITCH_CYCLE)]
            candidates.append(
                NoteCandidate(
                    midi=midi,
                    name=name,
                    start_seconds=round(start_seconds, 6),
                    end_seconds=round(end_seconds, 6),
                    confidence=0.35,
                ),
            )
        return candidates
