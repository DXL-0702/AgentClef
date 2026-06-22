import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from shared.schemas.score import CandidateEdit, DraftScore, Revision, SelectionRange


FIXTURE_PATH = Path("tests/fixtures/score_review_v01.json")


def load_fixture_bundle() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text())


def test_v01_fixture_bundle_validates_core_score_contracts() -> None:
    bundle = load_fixture_bundle()

    draft_score = DraftScore.model_validate(bundle["draft_score"])
    selection_range = SelectionRange.model_validate(bundle["selection_range"])
    candidate_edit = CandidateEdit.model_validate(bundle["candidate_edit"])
    revision = Revision.model_validate(bundle["revision"])

    assert draft_score.version == 1
    assert draft_score.notes[0].pitch.midi == 60
    assert selection_range.note_ids == ["note-3"]
    assert candidate_edit.operations[0].type.value == "change_duration"
    assert revision.source.value == "confirmed_agent_edit"


def test_draft_score_round_trip_keeps_valid_payload() -> None:
    bundle = load_fixture_bundle()

    validated = DraftScore.model_validate(bundle["draft_score"])
    round_trip = DraftScore.model_validate_json(validated.model_dump_json())

    assert round_trip == validated


def test_note_event_rejects_non_positive_audio_span() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["notes"][0]["audio_start_seconds"] = 0.25
    invalid_payload["notes"][0]["audio_end_seconds"] = invalid_payload["notes"][0]["audio_start_seconds"]

    with pytest.raises(ValueError, match="audio_end_seconds must be greater than audio_start_seconds"):
        DraftScore.model_validate(invalid_payload)


def test_selection_range_rejects_note_target_without_single_note_id() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["selection_range"])
    invalid_payload["note_ids"] = ["note-2", "note-3"]

    with pytest.raises(ValueError, match="note selection must include exactly one note_id"):
        SelectionRange.model_validate(invalid_payload)


def test_candidate_edit_rejects_empty_operations() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["candidate_edit"])
    invalid_payload["operations"] = []

    with pytest.raises(ValueError, match="at least 1 item"):
        CandidateEdit.model_validate(invalid_payload)


def test_candidate_edit_rejects_missing_note_id_for_duration_change() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["candidate_edit"])
    invalid_payload["operations"][0].pop("note_id")

    with pytest.raises(ValueError, match="change_duration operation must include note_id"):
        CandidateEdit.model_validate(invalid_payload)


def test_draft_score_rejects_chord_event_on_non_chord_track() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["chords"][0]["track_id"] = "track-main"

    with pytest.raises(ValueError, match="ChordEvent must reference a chords track"):
        DraftScore.model_validate(invalid_payload)


def test_draft_score_rejects_updated_at_before_created_at() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["updated_at"] = "2026-06-22T13:49:59Z"

    with pytest.raises(ValueError, match="updated_at must be greater than or equal to created_at"):
        DraftScore.model_validate(invalid_payload)


def test_draft_score_rejects_naive_timestamp() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["created_at"] = "2026-06-22T13:50:00"

    with pytest.raises(ValueError, match="timezone"):
        DraftScore.model_validate(invalid_payload)


def test_candidate_edit_rejects_naive_timestamp() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["candidate_edit"])
    invalid_payload["created_at"] = "2026-06-22T13:50:00"

    with pytest.raises(ValueError, match="timezone"):
        CandidateEdit.model_validate(invalid_payload)


def test_revision_rejects_naive_timestamp() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["revision"])
    invalid_payload["created_at"] = "2026-06-22T13:50:00"

    with pytest.raises(ValueError, match="timezone"):
        Revision.model_validate(invalid_payload)


def test_draft_score_rejects_duplicate_track_id() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["tracks"][1]["id"] = "track-main"

    with pytest.raises(ValueError, match="Track IDs must be unique within DraftScore"):
        DraftScore.model_validate(invalid_payload)


def test_draft_score_rejects_duplicate_note_id() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["notes"][1]["id"] = "note-1"

    with pytest.raises(ValueError, match="Duplicate NoteEvent ID found: note-1"):
        DraftScore.model_validate(invalid_payload)


def test_draft_score_rejects_duplicate_chord_id() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["draft_score"])
    duplicate_chord = deepcopy(invalid_payload["chords"][0])
    invalid_payload["chords"].append(duplicate_chord)

    with pytest.raises(ValueError, match="Duplicate ChordEvent ID found: chord-1"):
        DraftScore.model_validate(invalid_payload)


def test_draft_score_rejects_unknown_uncertainty_note_reference() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["uncertainty_markers"][0]["note_ids"] = ["missing-note"]

    with pytest.raises(ValueError, match="UncertaintyMarker references unknown note_id: missing-note"):
        DraftScore.model_validate(invalid_payload)


def test_draft_score_rejects_unknown_uncertainty_chord_reference() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["uncertainty_markers"][0]["chord_event_ids"] = ["missing-chord"]

    with pytest.raises(
        ValueError,
        match="UncertaintyMarker references unknown chord_event_id: missing-chord",
    ):
        DraftScore.model_validate(invalid_payload)


def test_beat_grid_rejects_non_increasing_index() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["beat_grid"]["beats"][1]["index"] = 0

    with pytest.raises(ValueError, match="beat index must be strictly increasing"):
        DraftScore.model_validate(invalid_payload)


def test_beat_grid_rejects_decreasing_measure() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["beat_grid"]["beats"][4]["measure"] = 0

    with pytest.raises(ValueError, match="Input should be greater than or equal to 1"):
        DraftScore.model_validate(invalid_payload)


def test_beat_grid_rejects_measure_regression() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["draft_score"])
    invalid_payload["beat_grid"]["beats"][4]["measure"] = 1
    invalid_payload["beat_grid"]["beats"][3]["measure"] = 2

    with pytest.raises(ValueError, match="beat measure must be non-decreasing"):
        DraftScore.model_validate(invalid_payload)


def test_selection_range_rejects_unrelated_chord_field_for_note_target() -> None:
    bundle = load_fixture_bundle()
    invalid_payload = deepcopy(bundle["selection_range"])
    invalid_payload["chord_event_id"] = "chord-1"

    with pytest.raises(
        ValueError,
        match="note selection must not include chord_event_id",
    ):
        SelectionRange.model_validate(invalid_payload)


def test_uncertainty_marker_rejects_missing_target() -> None:
    bundle = load_fixture_bundle()
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
