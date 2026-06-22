import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from shared.schemas.score import CandidateEdit, DraftScore, Revision, SelectionRange


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "score_review_v01.json"


def load_fixture_bundle() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bundle() -> dict[str, Any]:
    return load_fixture_bundle()


def test_v01_fixture_bundle_validates_core_score_contracts(bundle: dict[str, Any]) -> None:
    draft_score = DraftScore.model_validate(bundle["draft_score"])
    selection_range = SelectionRange.model_validate(bundle["selection_range"])
    candidate_edit = CandidateEdit.model_validate(bundle["candidate_edit"])
    revision = Revision.model_validate(bundle["revision"])

    assert draft_score.version == 1
    assert draft_score.notes[0].pitch.midi == 60
    assert selection_range.note_ids == ["note-3"]
    assert candidate_edit.operations[0].type.value == "change_duration"
    assert revision.source.value == "confirmed_agent_edit"


def test_draft_score_round_trip_keeps_valid_payload(bundle: dict[str, Any]) -> None:
    validated = DraftScore.model_validate(bundle["draft_score"])
    round_trip = DraftScore.model_validate_json(validated.model_dump_json())

    assert round_trip == validated


def test_note_event_rejects_non_positive_audio_span(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["notes"][0]["audio_start_seconds"] = 0.25
    invalid_payload["notes"][0]["audio_end_seconds"] = invalid_payload["notes"][0]["audio_start_seconds"]

    with pytest.raises(ValueError, match="audio_end_seconds must be greater than audio_start_seconds"):
        DraftScore.model_validate(invalid_payload)


def test_selection_range_rejects_note_target_without_single_note_id(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["selection_range"])
    invalid_payload["note_ids"] = ["note-2", "note-3"]

    with pytest.raises(ValueError, match="note selection must include exactly one note_id"):
        SelectionRange.model_validate(invalid_payload)


def test_candidate_edit_rejects_empty_operations(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["candidate_edit"])
    invalid_payload["operations"] = []

    with pytest.raises(ValueError, match="at least 1 item"):
        CandidateEdit.model_validate(invalid_payload)


def test_candidate_edit_rejects_missing_note_id_for_duration_change(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["candidate_edit"])
    invalid_payload["operations"][0].pop("note_id")

    with pytest.raises(ValueError, match="change_duration operation must include note_id"):
        CandidateEdit.model_validate(invalid_payload)


def test_candidate_edit_rejects_note_operation_with_chord_fields(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["candidate_edit"])
    invalid_payload["operations"][0]["chord_event_id"] = "chord-1"

    with pytest.raises(
        ValueError,
        match="change_duration operation must not include chord_event_id",
    ):
        CandidateEdit.model_validate(invalid_payload)


def test_candidate_edit_rejects_pitch_change_with_duration_fields(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["candidate_edit"])
    invalid_payload["operations"][0] = {
        "type": "change_pitch",
        "note_id": "note-1",
        "pitch": {
            "midi": 62,
            "name": "D4",
        },
        "duration_beats": 1.5,
    }

    with pytest.raises(
        ValueError,
        match="change_pitch operation must not include duration_beats",
    ):
        CandidateEdit.model_validate(invalid_payload)


def test_candidate_edit_rejects_duration_change_with_pitch_field(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["candidate_edit"])
    invalid_payload["operations"][0]["pitch"] = {
        "midi": 62,
        "name": "D4",
    }

    with pytest.raises(
        ValueError,
        match="change_duration operation must not include pitch",
    ):
        CandidateEdit.model_validate(invalid_payload)


def test_candidate_edit_rejects_move_note_with_duration_field(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["candidate_edit"])
    invalid_payload["operations"][0] = {
        "type": "move_note",
        "note_id": "note-1",
        "start_beat": 1.5,
        "duration_beats": 1.0,
    }

    with pytest.raises(
        ValueError,
        match="move_note operation must not include duration_beats",
    ):
        CandidateEdit.model_validate(invalid_payload)


def test_candidate_edit_rejects_delete_note_with_audio_range(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["candidate_edit"])
    invalid_payload["operations"][0] = {
        "type": "delete_note",
        "note_id": "note-1",
        "audio_range": {
            "start_seconds": 0.0,
            "end_seconds": 0.5,
        },
    }

    with pytest.raises(
        ValueError,
        match="delete_note operation must not include audio_range",
    ):
        CandidateEdit.model_validate(invalid_payload)


def test_candidate_edit_rejects_add_note_with_individual_note_fields(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["candidate_edit"])
    invalid_payload["operations"][0] = {
        "type": "add_note",
        "note_event": deepcopy(bundle["draft_score"]["notes"][0]),
        "pitch": {
            "midi": 62,
            "name": "D4",
        },
    }

    with pytest.raises(
        ValueError,
        match="add_note operation must not include pitch",
    ):
        CandidateEdit.model_validate(invalid_payload)


def test_candidate_edit_rejects_change_chord_with_note_fields(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["candidate_edit"])
    invalid_payload["operations"][0] = {
        "type": "change_chord",
        "chord_event_id": "chord-1",
        "chord_label": "Am",
        "note_id": "note-1",
    }

    with pytest.raises(
        ValueError,
        match="change_chord operation must not include note_id",
    ):
        CandidateEdit.model_validate(invalid_payload)


def test_draft_score_rejects_chord_event_on_non_chord_track(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["chords"][0]["track_id"] = "track-main"

    with pytest.raises(ValueError, match="ChordEvent must reference a chords track"):
        DraftScore.model_validate(invalid_payload)


def test_draft_score_rejects_updated_at_before_created_at(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["updated_at"] = "2026-06-22T13:49:59Z"

    with pytest.raises(ValueError, match="updated_at must be greater than or equal to created_at"):
        DraftScore.model_validate(invalid_payload)


def test_draft_score_rejects_naive_timestamp(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["created_at"] = "2026-06-22T13:50:00"

    with pytest.raises(ValueError, match="timezone"):
        DraftScore.model_validate(invalid_payload)


def test_candidate_edit_rejects_naive_timestamp(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["candidate_edit"])
    invalid_payload["created_at"] = "2026-06-22T13:50:00"

    with pytest.raises(ValueError, match="timezone"):
        CandidateEdit.model_validate(invalid_payload)


def test_revision_rejects_naive_timestamp(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["revision"])
    invalid_payload["created_at"] = "2026-06-22T13:50:00"

    with pytest.raises(ValueError, match="timezone"):
        Revision.model_validate(invalid_payload)


def test_draft_score_rejects_duplicate_track_id(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["tracks"][1]["id"] = "track-main"

    with pytest.raises(ValueError, match="Track IDs must be unique within DraftScore"):
        DraftScore.model_validate(invalid_payload)


def test_draft_score_rejects_duplicate_note_id(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["notes"][1]["id"] = "note-1"

    with pytest.raises(ValueError, match="Duplicate NoteEvent ID found: note-1"):
        DraftScore.model_validate(invalid_payload)


def test_draft_score_rejects_duplicate_chord_id(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    duplicate_chord = deepcopy(invalid_payload["chords"][0])
    invalid_payload["chords"].append(duplicate_chord)

    with pytest.raises(ValueError, match="Duplicate ChordEvent ID found: chord-1"):
        DraftScore.model_validate(invalid_payload)


def test_draft_score_rejects_duplicate_uncertainty_marker_id(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    duplicate_marker = deepcopy(invalid_payload["uncertainty_markers"][0])
    invalid_payload["uncertainty_markers"].append(duplicate_marker)

    with pytest.raises(ValueError, match="Duplicate UncertaintyMarker ID found: uncertain-1"):
        DraftScore.model_validate(invalid_payload)


def test_draft_score_rejects_unknown_uncertainty_note_reference(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["uncertainty_markers"][0]["note_ids"] = ["missing-note"]

    with pytest.raises(ValueError, match="UncertaintyMarker references unknown note_id: missing-note"):
        DraftScore.model_validate(invalid_payload)


def test_draft_score_rejects_unknown_uncertainty_chord_reference(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["uncertainty_markers"][0]["chord_event_ids"] = ["missing-chord"]

    with pytest.raises(
        ValueError,
        match="UncertaintyMarker references unknown chord_event_id: missing-chord",
    ):
        DraftScore.model_validate(invalid_payload)


def test_beat_grid_rejects_non_increasing_index(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["beat_grid"]["beats"][1]["index"] = 0

    with pytest.raises(ValueError, match="beat index must be strictly increasing"):
        DraftScore.model_validate(invalid_payload)


def test_beat_grid_rejects_non_power_of_two_denominator(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["beat_grid"]["meter_denominator"] = 3

    with pytest.raises(ValueError, match="meter_denominator must be a power of 2"):
        DraftScore.model_validate(invalid_payload)


def test_beat_grid_rejects_decreasing_measure(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["beat_grid"]["beats"][4]["measure"] = 0

    with pytest.raises(ValueError, match="Input should be greater than or equal to 1"):
        DraftScore.model_validate(invalid_payload)


def test_beat_grid_rejects_measure_regression(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["beat_grid"]["beats"][4]["measure"] = 1
    invalid_payload["beat_grid"]["beats"][3]["measure"] = 2

    with pytest.raises(ValueError, match="beat measure must be non-decreasing"):
        DraftScore.model_validate(invalid_payload)


def test_selection_range_rejects_unrelated_chord_field_for_note_target(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["selection_range"])
    invalid_payload["chord_event_id"] = "chord-1"

    with pytest.raises(
        ValueError,
        match="note selection must not include chord_event_id",
    ):
        SelectionRange.model_validate(invalid_payload)


def test_uncertainty_marker_rejects_missing_target(bundle: dict[str, Any]) -> None:
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["uncertainty_markers"][0].pop("audio_range")
    invalid_payload["uncertainty_markers"][0].pop("beat_range")
    invalid_payload["uncertainty_markers"][0]["note_ids"] = []
    invalid_payload["uncertainty_markers"][0]["chord_event_ids"] = []

    with pytest.raises(
        ValueError,
        match="UncertaintyMarker must have at least one target",
    ):
        DraftScore.model_validate(invalid_payload)
