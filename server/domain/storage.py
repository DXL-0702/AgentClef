from pathlib import Path
from uuid import uuid4

import anyio
from fastapi import UploadFile


ALLOWED_AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".wav",
    ".webm",
}

ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/aac",
    "audio/aiff",
    "audio/flac",
    "audio/m4a",
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/wav",
    "audio/wave",
    "audio/webm",
    "audio/x-aiff",
    "audio/x-m4a",
    "audio/x-wav",
    "application/octet-stream",
}

CHUNK_SIZE_BYTES = 1024 * 1024


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
    ) -> None:
        self.original_filename = original_filename
        self.stored_filename = stored_filename
        self.content_type = content_type
        self.extension = extension
        self.size_bytes = size_bytes


def validate_audio_upload_metadata(file: UploadFile) -> tuple[str, str, str]:
    original_filename = Path(file.filename or "").name
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
) -> StoredUpload:
    destination: Path | None = None
    try:
        original_filename, extension, content_type = validate_audio_upload_metadata(file)
        project_dir = (storage_root / "projects" / project_id / "audio").resolve()
        storage_root_resolved = storage_root.resolve()
        if not project_dir.is_relative_to(storage_root_resolved):
            raise UploadValidationError("invalid storage path")

        project_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{uuid4().hex}{extension}"
        destination = (project_dir / stored_filename).resolve()
        if not destination.is_relative_to(project_dir):
            raise UploadValidationError("invalid destination path")

        size_bytes = 0
        async with await anyio.open_file(destination, "wb") as output:
            while chunk := await file.read(CHUNK_SIZE_BYTES):
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise UploadValidationError("audio file exceeds upload size limit")
                await output.write(chunk)

        if size_bytes == 0:
            destination.unlink(missing_ok=True)
            raise UploadValidationError("audio file must not be empty")

        return StoredUpload(
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_type=content_type,
            extension=extension,
            size_bytes=size_bytes,
        )
    except Exception:
        if destination is not None:
            destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
