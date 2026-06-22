import shutil
import subprocess
import wave
from dataclasses import dataclass
from functools import lru_cache, partial
from pathlib import Path
from uuid import uuid4

import anyio
from fastapi import UploadFile


CHUNK_SIZE_BYTES = 1024 * 1024
MEDIA_SIGNATURE_BYTES = 4096


@dataclass(frozen=True)
class AudioFormatSpec:
    canonical_content_type: str
    extensions: frozenset[str]
    content_types: frozenset[str]


AUDIO_FORMATS = {
    "aac": AudioFormatSpec(
        canonical_content_type="audio/aac",
        extensions=frozenset({".aac"}),
        content_types=frozenset({"audio/aac", "application/octet-stream"}),
    ),
    "aiff": AudioFormatSpec(
        canonical_content_type="audio/aiff",
        extensions=frozenset({".aif", ".aiff"}),
        content_types=frozenset({"audio/aiff", "audio/x-aiff", "application/octet-stream"}),
    ),
    "flac": AudioFormatSpec(
        canonical_content_type="audio/flac",
        extensions=frozenset({".flac"}),
        content_types=frozenset({"audio/flac", "application/octet-stream"}),
    ),
    "m4a": AudioFormatSpec(
        canonical_content_type="audio/m4a",
        extensions=frozenset({".m4a"}),
        content_types=frozenset({"audio/m4a", "audio/x-m4a", "application/octet-stream"}),
    ),
    "mp3": AudioFormatSpec(
        canonical_content_type="audio/mpeg",
        extensions=frozenset({".mp3"}),
        content_types=frozenset({"audio/mpeg", "audio/mp3", "application/octet-stream"}),
    ),
    "ogg": AudioFormatSpec(
        canonical_content_type="audio/ogg",
        extensions=frozenset({".ogg"}),
        content_types=frozenset({"audio/ogg", "application/octet-stream"}),
    ),
    "wav": AudioFormatSpec(
        canonical_content_type="audio/wav",
        extensions=frozenset({".wav"}),
        content_types=frozenset(
            {"audio/wav", "audio/wave", "audio/x-wav", "application/octet-stream"},
        ),
    ),
    "webm": AudioFormatSpec(
        canonical_content_type="audio/webm",
        extensions=frozenset({".webm"}),
        content_types=frozenset({"audio/webm", "application/octet-stream"}),
    ),
}

ALLOWED_AUDIO_EXTENSIONS = frozenset(
    extension
    for format_spec in AUDIO_FORMATS.values()
    for extension in format_spec.extensions
)
ALLOWED_AUDIO_CONTENT_TYPES = frozenset(
    content_type
    for format_spec in AUDIO_FORMATS.values()
    for content_type in format_spec.content_types
)


def _mkdir_parents(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _unlink_missing_ok(path: Path) -> None:
    path.unlink(missing_ok=True)


class UploadValidationError(ValueError):
    pass


class StoredUpload:
    def __init__(
        self,
        *,
        original_filename: str,
        stored_filename: str,
        content_type: str,
        extension: str,
        size_bytes: int,
        duration_seconds: float,
    ) -> None:
        self.original_filename = original_filename
        self.stored_filename = stored_filename
        self.content_type = content_type
        self.extension = extension
        self.size_bytes = size_bytes
        self.duration_seconds = duration_seconds


def validate_audio_upload_metadata(file: UploadFile) -> tuple[str, str, str]:
    filename = file.filename or ""
    original_filename = Path(filename.replace("\\", "/")).name
    if not original_filename:
        raise UploadValidationError("audio file name is required")

    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_AUDIO_EXTENSIONS:
        raise UploadValidationError("unsupported audio file extension")

    content_type = (file.content_type or "application/octet-stream").lower()
    if content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise UploadValidationError("unsupported audio content type")

    return original_filename, extension, content_type


async def store_audio_upload(
    *,
    file: UploadFile,
    storage_root: Path,
    project_id: str,
    max_bytes: int,
    max_seconds: int,
) -> StoredUpload:
    destination: Path | None = None
    try:
        original_filename, extension, declared_content_type = validate_audio_upload_metadata(file)
        project_dir = (storage_root / "projects" / project_id / "audio").resolve()
        storage_root_resolved = storage_root.resolve()
        if not project_dir.is_relative_to(storage_root_resolved):
            raise UploadValidationError("invalid storage path")

        await anyio.to_thread.run_sync(_mkdir_parents, project_dir)

        stored_filename = f"{uuid4().hex}{extension}"
        destination = (project_dir / stored_filename).resolve()
        if not destination.is_relative_to(project_dir):
            raise UploadValidationError("invalid destination path")

        size_bytes = 0
        signature_bytes = bytearray()
        async with await anyio.open_file(destination, "wb") as output:
            while chunk := await file.read(CHUNK_SIZE_BYTES):
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise UploadValidationError("audio file exceeds upload size limit")
                if len(signature_bytes) < MEDIA_SIGNATURE_BYTES:
                    remaining_signature_bytes = MEDIA_SIGNATURE_BYTES - len(signature_bytes)
                    signature_bytes.extend(chunk[:remaining_signature_bytes])
                await output.write(chunk)

        if size_bytes == 0:
            await anyio.to_thread.run_sync(_unlink_missing_ok, destination)
            raise UploadValidationError("audio file must not be empty")

        actual_format = detect_audio_format(bytes(signature_bytes))
        if actual_format is None:
            raise UploadValidationError("unsupported actual audio media type")
        if extension not in actual_format.extensions:
            raise UploadValidationError("audio file content does not match extension")
        if declared_content_type not in actual_format.content_types:
            raise UploadValidationError("audio content type does not match file content")
        duration_seconds = await anyio.to_thread.run_sync(
            partial(get_audio_duration_seconds, destination=destination, format_spec=actual_format),
        )
        if duration_seconds > max_seconds:
            raise UploadValidationError("audio file exceeds upload duration limit")

        return StoredUpload(
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_type=actual_format.canonical_content_type,
            extension=extension,
            size_bytes=size_bytes,
            duration_seconds=duration_seconds,
        )
    except Exception:
        if destination is not None:
            await anyio.to_thread.run_sync(_unlink_missing_ok, destination)
        raise
    finally:
        await file.close()


async def delete_stored_upload(
    *,
    storage_root: Path,
    project_id: str,
    stored_filename: str,
) -> None:
    project_dir = (storage_root / "projects" / project_id / "audio").resolve()
    storage_root_resolved = storage_root.resolve()
    if not project_dir.is_relative_to(storage_root_resolved):
        raise UploadValidationError("invalid storage path")

    normalized_stored_filename = Path(stored_filename.replace("\\", "/")).name
    if normalized_stored_filename != stored_filename:
        raise UploadValidationError("invalid stored file name")

    destination = (project_dir / stored_filename).resolve()
    if not destination.is_relative_to(project_dir):
        raise UploadValidationError("invalid destination path")

    await anyio.to_thread.run_sync(_unlink_missing_ok, destination)


def detect_audio_format(header: bytes) -> AudioFormatSpec | None:
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return AUDIO_FORMATS["wav"]
    if len(header) >= 12 and header[:4] == b"FORM" and header[8:12] in {b"AIFF", b"AIFC"}:
        return AUDIO_FORMATS["aiff"]
    if header.startswith(b"fLaC"):
        return AUDIO_FORMATS["flac"]
    if header.startswith(b"OggS"):
        return AUDIO_FORMATS["ogg"]
    if len(header) >= 4 and header[:4] == b"\x1a\x45\xdf\xa3" and b"webm" in header[:128].lower():
        return AUDIO_FORMATS["webm"]
    if len(header) >= 12 and header[4:8] == b"ftyp" and _is_m4a_brand(header[8:32]):
        return AUDIO_FORMATS["m4a"]
    if len(header) >= 3 and header[:3] == b"ID3":
        return AUDIO_FORMATS["mp3"]
    if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xF6) == 0xF0:
        return AUDIO_FORMATS["aac"]
    if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
        return AUDIO_FORMATS["mp3"]
    return None


def get_audio_duration_seconds(*, destination: Path, format_spec: AudioFormatSpec) -> float:
    duration_seconds: float | None = None
    if format_spec is AUDIO_FORMATS["wav"]:
        duration_seconds = _get_wav_duration_seconds(destination)
    else:
        duration_seconds = _get_ffprobe_duration_seconds(destination)

    if duration_seconds is None or duration_seconds <= 0:
        raise UploadValidationError("audio duration could not be determined")
    return duration_seconds


def _get_wav_duration_seconds(destination: Path) -> float:
    try:
        with wave.open(str(destination), "rb") as wav_file:
            frame_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            if frame_rate <= 0 or frame_count <= 0:
                raise UploadValidationError("audio duration could not be determined")
            return frame_count / float(frame_rate)
    except UploadValidationError:
        raise
    except Exception as exc:
        raise UploadValidationError("audio duration could not be determined") from exc


def _is_m4a_brand(brand_bytes: bytes) -> bool:
    return any(
        brand in brand_bytes
        for brand in (
            b"M4A ",
            b"M4B ",
            b"mp41",
            b"mp42",
            b"isom",
        )
    )


@lru_cache
def get_ffprobe_path() -> str | None:
    return shutil.which("ffprobe")


def _get_ffprobe_duration_seconds(destination: Path) -> float | None:
    ffprobe_path = get_ffprobe_path()
    if ffprobe_path is None:
        return None

    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(destination),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None

    output = result.stdout.strip()
    if not output:
        return None
    try:
        return float(output)
    except ValueError:
        return None
