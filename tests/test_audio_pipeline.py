import io
import wave
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pytest import MonkeyPatch

from worker.pipeline.audio import (
    AudioPipelineError,
    MAX_FFMPEG_ERROR_DETAIL_LENGTH,
    build_normalized_audio_path,
    normalize_audio_to_wav,
    resolve_stored_audio_path,
)


def build_wav_bytes(*, duration_seconds: float = 0.25, sample_rate: int = 8_000) -> bytes:
    frame_count = int(duration_seconds * sample_rate)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)
    return buffer.getvalue()


def test_normalize_wav_uses_ffmpeg_when_available(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source_path = tmp_path / "source.wav"
    destination_path = tmp_path / "normalized.wav"
    captured_command: list[str] = []
    source_path.write_bytes(build_wav_bytes(duration_seconds=0.5, sample_rate=8_000))

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured_command.extend(command)
        destination_path.write_bytes(build_wav_bytes(duration_seconds=0.5, sample_rate=44_100))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("worker.pipeline.audio.get_ffmpeg_path", lambda: "/usr/bin/ffmpeg")
    monkeypatch.setattr("worker.pipeline.audio.subprocess.run", fake_run)

    normalized_audio = normalize_audio_to_wav(
        source_path=source_path,
        destination_path=destination_path,
    )

    assert normalized_audio.path == destination_path
    assert normalized_audio.duration_seconds == 0.5
    assert normalized_audio.sample_rate == 44_100
    assert captured_command[0] == "/usr/bin/ffmpeg"


def test_normalize_wav_falls_back_to_copy_when_ffmpeg_is_missing(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source_path = tmp_path / "source.wav"
    destination_path = tmp_path / "normalized.wav"
    source_path.write_bytes(build_wav_bytes(duration_seconds=0.5, sample_rate=8_000))
    monkeypatch.setattr("worker.pipeline.audio.get_ffmpeg_path", lambda: None)

    normalized_audio = normalize_audio_to_wav(
        source_path=source_path,
        destination_path=destination_path,
    )

    assert destination_path.is_file()
    assert normalized_audio.path == destination_path
    assert normalized_audio.duration_seconds == 0.5
    assert normalized_audio.sample_rate == 8_000
    assert normalized_audio.channel_count == 1


def test_normalize_audio_uses_hardened_ffmpeg_command(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source_path = tmp_path / "source.mp3"
    destination_path = tmp_path / "normalized.wav"
    captured_command: list[str] = []
    captured_kwargs: dict[str, object] = {}
    source_path.write_bytes(b"fake mp3 bytes")

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured_command.extend(command)
        captured_kwargs.update(kwargs)
        destination_path.write_bytes(build_wav_bytes())
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("worker.pipeline.audio.get_ffmpeg_path", lambda: "/usr/bin/ffmpeg")
    monkeypatch.setattr("worker.pipeline.audio.subprocess.run", fake_run)

    normalized_audio = normalize_audio_to_wav(
        source_path=source_path,
        destination_path=destination_path,
    )

    assert normalized_audio.path == destination_path
    assert captured_command == [
        "/usr/bin/ffmpeg",
        "-nostdin",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-map",
        "0:a:0",
        "-ac",
        "1",
        "-ar",
        "44100",
        "-acodec",
        "pcm_s16le",
        "-f",
        "wav",
        str(destination_path),
    ]
    assert captured_kwargs["text"] is True
    assert captured_kwargs["errors"] == "replace"


def test_normalize_audio_includes_truncated_ffmpeg_stderr(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source_path = tmp_path / "source.mp3"
    destination_path = tmp_path / "normalized.wav"
    stderr = "codec failure: " + ("x" * (MAX_FFMPEG_ERROR_DETAIL_LENGTH + 100))
    source_path.write_bytes(b"fake mp3 bytes")

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=1, stderr=stderr)

    monkeypatch.setattr("worker.pipeline.audio.get_ffmpeg_path", lambda: "/usr/bin/ffmpeg")
    monkeypatch.setattr("worker.pipeline.audio.subprocess.run", fake_run)

    with pytest.raises(AudioPipelineError) as exc_info:
        normalize_audio_to_wav(
            source_path=source_path,
            destination_path=destination_path,
        )

    error_message = str(exc_info.value)
    assert error_message.startswith("audio normalization failed: codec failure:")
    assert error_message.endswith("...")
    assert len(error_message) <= len("audio normalization failed: ") + (
        MAX_FFMPEG_ERROR_DETAIL_LENGTH + 3
    )


def test_resolve_stored_audio_path_rejects_path_traversal(tmp_path: Path) -> None:
    project_id = uuid4()
    storage_root = tmp_path / "storage"
    audio_dir = storage_root / "projects" / str(project_id) / "audio"
    audio_dir.mkdir(parents=True)
    (tmp_path / "escape.wav").write_bytes(build_wav_bytes())

    with pytest.raises(AudioPipelineError, match="invalid stored audio filename"):
        resolve_stored_audio_path(
            storage_root=storage_root,
            project_id=project_id,
            stored_filename="../escape.wav",
        )


def test_resolve_stored_audio_path_rejects_backslash_segments(tmp_path: Path) -> None:
    project_id = uuid4()
    storage_root = tmp_path / "storage"

    with pytest.raises(AudioPipelineError, match="invalid stored audio filename"):
        resolve_stored_audio_path(
            storage_root=storage_root,
            project_id=project_id,
            stored_filename="nested\\escape.wav",
        )


def test_build_normalized_audio_path_stays_under_storage_root(tmp_path: Path) -> None:
    project_id = uuid4()
    job_id = uuid4()
    storage_root = tmp_path / "storage"

    normalized_path = build_normalized_audio_path(
        storage_root=storage_root,
        project_id=project_id,
        job_id=job_id,
    )

    assert (
        normalized_path
        == (
            storage_root
            / "projects"
            / str(project_id)
            / "pipeline"
            / str(job_id)
            / "normalized.wav"
        ).resolve()
    )
    assert normalized_path.parent.is_dir()
