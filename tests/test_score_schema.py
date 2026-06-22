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
