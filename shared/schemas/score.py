from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrackKind(StrEnum):
    main_melody = "main_melody"
    chords = "chords"


class EventSource(StrEnum):
    model = "model"
    user = "user"
    confirmed_agent_edit = "confirmed_agent_edit"


class UncertaintyType(StrEnum):
    pitch_uncertain = "pitch_uncertain"
    rhythm_uncertain = "rhythm_uncertain"
    duration_uncertain = "duration_uncertain"
    chord_uncertain = "chord_uncertain"
    beat_alignment_uncertain = "beat_alignment_uncertain"


class SelectionTargetType(StrEnum):
    note = "note"
    notes = "notes"
    measure_range = "measure_range"
    time_range = "time_range"
    chord = "chord"
    uncertainty_marker = "uncertainty_marker"


class CandidateEditType(StrEnum):
    change_pitch = "change_pitch"
    change_duration = "change_duration"
    move_note = "move_note"
    add_note = "add_note"
    delete_note = "delete_note"
    change_chord = "change_chord"


class CandidateEditStatus(StrEnum):
    proposed = "proposed"
    accepted = "accepted"
    rejected = "rejected"
    applied = "applied"


class RevisionSource(StrEnum):
    user = "user"
    confirmed_agent_edit = "confirmed_agent_edit"
    system = "system"


OperationField = Literal[
    "note_id",
    "chord_event_id",
    "pitch",
    "duration_beats",
    "start_beat",
    "audio_range",
    "note_event",
    "chord_label",
]


@dataclass(frozen=True)
class OperationContract:
    required: tuple[OperationField, ...]
    forbidden: tuple[OperationField, ...]


OPERATION_CONTRACTS: dict[CandidateEditType, OperationContract] = {
    CandidateEditType.change_pitch: OperationContract(
        required=("note_id", "pitch"),
        forbidden=("duration_beats", "start_beat", "chord_event_id", "chord_label", "note_event"),
    ),
    CandidateEditType.change_duration: OperationContract(
        required=("note_id", "duration_beats"),
        forbidden=("pitch", "start_beat", "chord_event_id", "chord_label", "note_event"),
    ),
    CandidateEditType.move_note: OperationContract(
        required=("note_id", "start_beat"),
        forbidden=("pitch", "duration_beats", "chord_event_id", "chord_label", "note_event"),
    ),
    CandidateEditType.add_note: OperationContract(
        required=("note_event",),
        forbidden=("note_id", "chord_event_id", "chord_label", "pitch", "duration_beats", "start_beat"),
    ),
    CandidateEditType.delete_note: OperationContract(
        required=("note_id",),
        forbidden=(
            "pitch",
            "duration_beats",
            "start_beat",
            "audio_range",
            "chord_event_id",
            "chord_label",
            "note_event",
        ),
    ),
    CandidateEditType.change_chord: OperationContract(
        required=("chord_event_id", "chord_label"),
        forbidden=("note_id", "pitch", "duration_beats", "start_beat", "note_event"),
    ),
}


class Confidence(StrictSchema):
    overall: float = Field(ge=0, le=1)
    pitch: float | None = Field(default=None, ge=0, le=1)
    onset: float | None = Field(default=None, ge=0, le=1)
    duration: float | None = Field(default=None, ge=0, le=1)


class Pitch(StrictSchema):
    midi: int = Field(ge=0, le=127)
    name: str | None = Field(default=None, min_length=1)


class AudioTimeRange(StrictSchema):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        return self


class BeatRange(StrictSchema):
    start_beat: float = Field(ge=0)
    end_beat: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end_beat <= self.start_beat:
            raise ValueError("end_beat must be greater than start_beat")
        return self


class MeasureRange(StrictSchema):
    start_measure: int = Field(ge=1)
    end_measure: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.end_measure < self.start_measure:
            raise ValueError("end_measure must be greater than or equal to start_measure")
        return self


class BeatPoint(StrictSchema):
    index: int = Field(ge=0)
    time_seconds: float = Field(ge=0)
    beat: float = Field(ge=0)
    measure: int = Field(ge=1)
    confidence: float | None = Field(default=None, ge=0, le=1)


class BeatGrid(StrictSchema):
    tempo_bpm: float = Field(gt=0)
    meter_numerator: int = Field(ge=1)
    meter_denominator: int = Field(ge=1)
    beats: list[BeatPoint] = Field(min_length=1)
    confidence: Confidence | None = None

    @model_validator(mode="after")
    def validate_monotonic_beats(self) -> Self:
        if self.meter_denominator & (self.meter_denominator - 1) != 0:
            raise ValueError("meter_denominator must be a power of 2")

        for previous, current in zip(self.beats, self.beats[1:], strict=False):
            if current.index <= previous.index:
                raise ValueError("beat index must be strictly increasing")
            if current.time_seconds <= previous.time_seconds:
                raise ValueError("beat time_seconds must be strictly increasing")
            if current.beat <= previous.beat:
                raise ValueError("beat positions must be strictly increasing")
            if current.measure < previous.measure:
                raise ValueError("beat measure must be non-decreasing")
        return self


class Track(StrictSchema):
    id: str = Field(min_length=1)
    kind: TrackKind
    name: str = Field(min_length=1)


class NoteEvent(StrictSchema):
    id: str = Field(min_length=1)
    track_id: str = Field(min_length=1)
    pitch: Pitch
    audio_start_seconds: float = Field(ge=0)
    audio_end_seconds: float = Field(gt=0)
    start_beat: float = Field(ge=0)
    duration_beats: float = Field(gt=0)
    source: EventSource
    confidence: Confidence | None = None
    notation_hints: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_audio_range(self) -> Self:
        if self.audio_end_seconds <= self.audio_start_seconds:
            raise ValueError("audio_end_seconds must be greater than audio_start_seconds")
        return self


class ChordEvent(StrictSchema):
    id: str = Field(min_length=1)
    track_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    candidate_labels: list[str] = Field(default_factory=list)
    audio_start_seconds: float = Field(ge=0)
    audio_end_seconds: float = Field(gt=0)
    start_beat: float = Field(ge=0)
    duration_beats: float = Field(gt=0)
    source: EventSource
    confidence: Confidence | None = None

    @model_validator(mode="after")
    def validate_audio_range(self) -> Self:
        if self.audio_end_seconds <= self.audio_start_seconds:
            raise ValueError("audio_end_seconds must be greater than audio_start_seconds")
        return self


class SelectionRange(StrictSchema):
    target_type: SelectionTargetType
    note_ids: list[str] = Field(default_factory=list)
    chord_event_id: str | None = Field(default=None, min_length=1)
    uncertainty_marker_id: str | None = Field(default=None, min_length=1)
    audio_range: AudioTimeRange | None = None
    beat_range: BeatRange | None = None
    measure_range: MeasureRange | None = None

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        if self.target_type == SelectionTargetType.note:
            if len(self.note_ids) != 1:
                raise ValueError("note selection must include exactly one note_id")
            if self.chord_event_id or self.uncertainty_marker_id or self.measure_range:
                raise ValueError(
                    "note selection must not include chord_event_id, "
                    "uncertainty_marker_id, or measure_range",
                )
        elif self.target_type == SelectionTargetType.notes:
            if not self.note_ids:
                raise ValueError("notes selection must include at least one note_id")
            if self.chord_event_id or self.uncertainty_marker_id or self.measure_range:
                raise ValueError(
                    "notes selection must not include chord_event_id, "
                    "uncertainty_marker_id, or measure_range",
                )
        elif self.target_type == SelectionTargetType.chord:
            if self.chord_event_id is None:
                raise ValueError("chord selection must include chord_event_id")
            if self.note_ids or self.uncertainty_marker_id or self.measure_range:
                raise ValueError(
                    "chord selection must not include note_ids, "
                    "uncertainty_marker_id, or measure_range",
                )
        elif self.target_type == SelectionTargetType.uncertainty_marker:
            if self.uncertainty_marker_id is None:
                raise ValueError("uncertainty_marker selection must include uncertainty_marker_id")
            if self.note_ids or self.chord_event_id or self.measure_range:
                raise ValueError(
                    "uncertainty_marker selection must not include note_ids, "
                    "chord_event_id, or measure_range",
                )
        elif self.target_type == SelectionTargetType.measure_range:
            if self.measure_range is None:
                raise ValueError("measure_range selection must include measure_range")
            if self.note_ids or self.chord_event_id or self.uncertainty_marker_id:
                raise ValueError(
                    "measure_range selection must not include note_ids, "
                    "chord_event_id, or uncertainty_marker_id",
                )
        elif self.target_type == SelectionTargetType.time_range:
            if self.audio_range is None and self.beat_range is None:
                raise ValueError("time_range selection must include audio_range or beat_range")
            if self.note_ids or self.chord_event_id or self.uncertainty_marker_id or self.measure_range:
                raise ValueError(
                    "time_range selection must not include note_ids, chord_event_id, "
                    "uncertainty_marker_id, or measure_range",
                )
        return self


class UncertaintyMarker(StrictSchema):
    id: str = Field(min_length=1)
    type: UncertaintyType
    message: str = Field(min_length=1)
    audio_range: AudioTimeRange | None = None
    beat_range: BeatRange | None = None
    note_ids: list[str] = Field(default_factory=list)
    chord_event_ids: list[str] = Field(default_factory=list)
    confidence: Confidence | None = None

    @model_validator(mode="after")
    def validate_has_target(self) -> Self:
        if (
            self.audio_range is None
            and self.beat_range is None
            and not self.note_ids
            and not self.chord_event_ids
        ):
            raise ValueError(
                "UncertaintyMarker must have at least one target: "
                "audio_range, beat_range, note_ids, or chord_event_ids",
            )
        return self


class CandidateEditOperation(StrictSchema):
    type: CandidateEditType
    note_id: str | None = Field(default=None, min_length=1)
    chord_event_id: str | None = Field(default=None, min_length=1)
    pitch: Pitch | None = None
    duration_beats: float | None = Field(default=None, gt=0)
    start_beat: float | None = Field(default=None, ge=0)
    audio_range: AudioTimeRange | None = None
    note_event: NoteEvent | None = None
    chord_label: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_operation_payload(self) -> Self:
        contract = OPERATION_CONTRACTS[self.type]
        self._validate_required_fields(contract.required)
        self._validate_forbidden_fields(contract.forbidden)
        return self

    def _validate_required_fields(self, required_fields: tuple[OperationField, ...]) -> None:
        for field_name in required_fields:
            if getattr(self, field_name) is None:
                raise ValueError(f"{self.type.value} operation must include {field_name}")

    def _validate_forbidden_fields(self, forbidden_fields: tuple[OperationField, ...]) -> None:
        present_fields = [field_name for field_name in forbidden_fields if getattr(self, field_name) is not None]
        if present_fields:
            raise ValueError(
                f"{self.type.value} operation must not include {self._format_field_list(present_fields)}",
            )

    @staticmethod
    def _format_field_list(field_names: list[OperationField]) -> str:
        if len(field_names) == 1:
            return field_names[0]
        if len(field_names) == 2:
            return f"{field_names[0]} or {field_names[1]}"
        return f"{', '.join(field_names[:-1])}, or {field_names[-1]}"


class CandidateEdit(StrictSchema):
    id: UUID
    draft_score_id: UUID
    draft_score_version: int = Field(ge=1)
    status: CandidateEditStatus = CandidateEditStatus.proposed
    summary: str = Field(min_length=1, max_length=255)
    affected_range: SelectionRange
    operations: list[CandidateEditOperation] = Field(min_length=1)
    created_at: AwareDatetime


class Revision(StrictSchema):
    id: UUID
    draft_score_id: UUID
    draft_score_version: int = Field(ge=1)
    source: RevisionSource
    summary: str = Field(min_length=1, max_length=255)
    affected_range: SelectionRange
    operations: list[CandidateEditOperation] = Field(default_factory=list)
    candidate_edit_id: UUID | None = None
    created_at: AwareDatetime


class DraftScore(StrictSchema):
    id: UUID
    project_id: UUID
    version: int = Field(ge=1)
    beat_grid: BeatGrid
    tracks: list[Track] = Field(min_length=1)
    notes: list[NoteEvent] = Field(default_factory=list)
    chords: list[ChordEvent] = Field(default_factory=list)
    uncertainty_markers: list[UncertaintyMarker] = Field(default_factory=list)
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_event_track_references(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be greater than or equal to created_at")

        track_ids = [track.id for track in self.tracks]
        if len(track_ids) != len(set(track_ids)):
            raise ValueError("Track IDs must be unique within DraftScore")

        tracks_by_id = {track.id: track for track in self.tracks}
        if not any(track.kind == TrackKind.main_melody for track in self.tracks):
            raise ValueError("DraftScore must include a main_melody track")

        note_ids: set[str] = set()
        for note in self.notes:
            if note.id in note_ids:
                raise ValueError(f"Duplicate NoteEvent ID found: {note.id}")
            note_ids.add(note.id)
            if note.track_id not in tracks_by_id:
                raise ValueError(f"NoteEvent references unknown track_id: {note.track_id}")
            if tracks_by_id[note.track_id].kind == TrackKind.chords:
                raise ValueError("NoteEvent must not reference a chords track")

        chord_ids: set[str] = set()
        for chord in self.chords:
            if chord.id in chord_ids:
                raise ValueError(f"Duplicate ChordEvent ID found: {chord.id}")
            chord_ids.add(chord.id)
            if chord.track_id not in tracks_by_id:
                raise ValueError(f"ChordEvent references unknown track_id: {chord.track_id}")
            if tracks_by_id[chord.track_id].kind != TrackKind.chords:
                raise ValueError("ChordEvent must reference a chords track")

        marker_ids: set[str] = set()
        for marker in self.uncertainty_markers:
            if marker.id in marker_ids:
                raise ValueError(f"Duplicate UncertaintyMarker ID found: {marker.id}")
            marker_ids.add(marker.id)
            for note_id in marker.note_ids:
                if note_id not in note_ids:
                    raise ValueError(f"UncertaintyMarker references unknown note_id: {note_id}")
            for chord_event_id in marker.chord_event_ids:
                if chord_event_id not in chord_ids:
                    raise ValueError(
                        f"UncertaintyMarker references unknown chord_event_id: {chord_event_id}",
                    )
        return self
