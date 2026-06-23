import shutil
import subprocess
import wave
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from uuid import UUID


MAX_FFMPEG_ERROR_DETAIL_LENGTH = 2_000


class AudioPipelineError(RuntimeError):
    pass


@dataclass(frozen=True, kw_only=True)
class NormalizedAudio:
    path: Path
    duration_seconds: float
    sample_rate: int
    channel_count: int


def resolve_stored_audio_path(
    *,
    storage_root: Path,
    project_id: UUID,
    stored_filename: str,
) -> Path:
    project_audio_dir = (storage_root / "projects" / str(project_id) / "audio").resolve()
    storage_root_resolved = storage_root.resolve()
    if not project_audio_dir.is_relative_to(storage_root_resolved):
        raise AudioPipelineError("invalid project audio path")

    normalized_stored_filename = Path(stored_filename.replace("\\", "/")).name
    if normalized_stored_filename != stored_filename:
        raise AudioPipelineError("invalid stored audio filename")

    audio_path = (project_audio_dir / stored_filename).resolve()
    if not audio_path.is_relative_to(project_audio_dir):
        raise AudioPipelineError("invalid stored audio path")
    if not audio_path.is_file():
        raise AudioPipelineError("stored audio file not found")
    return audio_path


def build_normalized_audio_path(
    *,
    storage_root: Path,
    project_id: UUID,
    job_id: UUID,
) -> Path:
    pipeline_dir = (
        storage_root / "projects" / str(project_id) / "pipeline" / str(job_id)
    ).resolve()
    storage_root_resolved = storage_root.resolve()
    if not pipeline_dir.is_relative_to(storage_root_resolved):
        raise AudioPipelineError("invalid pipeline path")
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    return pipeline_dir / "normalized.wav"


def normalize_audio_to_wav(*, source_path: Path, destination_path: Path) -> NormalizedAudio:
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is not None:
        _run_ffmpeg_normalization(ffmpeg_path, source_path, destination_path)
    elif source_path.suffix.lower() == ".wav":
        shutil.copyfile(source_path, destination_path)
    else:
        raise AudioPipelineError("ffmpeg is required to normalize non-WAV audio files")

    return read_wav_metadata(destination_path)


def read_wav_metadata(path: Path) -> NormalizedAudio:
    try:
        with wave.open(str(path), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            channel_count = wav_file.getnchannels()
    except Exception as exc:
        raise AudioPipelineError("normalized audio metadata could not be read") from exc

    if sample_rate <= 0 or frame_count <= 0 or channel_count <= 0:
        raise AudioPipelineError("normalized audio metadata is invalid")
    return NormalizedAudio(
        path=path,
        duration_seconds=frame_count / float(sample_rate),
        sample_rate=sample_rate,
        channel_count=channel_count,
    )


@lru_cache
def get_ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def _run_ffmpeg_normalization(
    ffmpeg_path: str,
    source_path: Path,
    destination_path: Path,
) -> None:
    try:
        result = subprocess.run(
            [
                ffmpeg_path,
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
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AudioPipelineError("audio normalization failed") from exc

    if result.returncode != 0:
        raise AudioPipelineError(_build_ffmpeg_error_message(result.stderr))


def _build_ffmpeg_error_message(stderr: str | None) -> str:
    detail = (stderr or "").strip()
    if not detail:
        return "audio normalization failed"
    if len(detail) > MAX_FFMPEG_ERROR_DETAIL_LENGTH:
        detail = f"{detail[:MAX_FFMPEG_ERROR_DETAIL_LENGTH]}..."
    return f"audio normalization failed: {detail}"
