from dataclasses import dataclass
from math import floor

from worker.pipeline.audio import NormalizedAudio


DEFAULT_TEMPO_BPM = 120.0
DEFAULT_METER_NUMERATOR = 4
DEFAULT_METER_DENOMINATOR = 4


@dataclass(frozen=True, kw_only=True)
class TimingAnalysis:
    duration_seconds: float
    tempo_bpm: float
    seconds_per_beat: float
    meter_numerator: int
    meter_denominator: int

    def __post_init__(self) -> None:
        if self.duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")
        if self.tempo_bpm <= 0:
            raise ValueError("tempo_bpm must be greater than 0")
        if self.seconds_per_beat <= 0:
            raise ValueError("seconds_per_beat must be greater than 0")
        if self.meter_numerator <= 0:
            raise ValueError("meter_numerator must be greater than 0")
        if self.meter_denominator <= 0:
            raise ValueError("meter_denominator must be greater than 0")


def analyze_timing(audio: NormalizedAudio) -> TimingAnalysis:
    tempo_bpm = DEFAULT_TEMPO_BPM
    return TimingAnalysis(
        duration_seconds=audio.duration_seconds,
        tempo_bpm=tempo_bpm,
        seconds_per_beat=60.0 / tempo_bpm,
        meter_numerator=DEFAULT_METER_NUMERATOR,
        meter_denominator=DEFAULT_METER_DENOMINATOR,
    )


def build_beat_points(analysis: TimingAnalysis) -> list[dict[str, int | float]]:
    beat_count = max(1, floor(analysis.duration_seconds / analysis.seconds_per_beat) + 1)
    return [
        {
            "index": index,
            "time_seconds": round(index * analysis.seconds_per_beat, 6),
            "beat": float(index),
            "measure": (index // analysis.meter_numerator) + 1,
            "confidence": 0.5,
        }
        for index in range(beat_count)
    ]
