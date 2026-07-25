import re
from pathlib import Path

from core.config import MAX_UPLOAD_BYTES
from fastapi import HTTPException, UploadFile, status

READ_CHUNK_BYTES = 1024 * 1024
_UNSAFE_FILENAME_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_upload_filename(filename: str | None) -> str:
    """Return a display-safe basename without trusting client path syntax."""

    normalized = (filename or "").replace("\\", "/")
    basename = normalized.rsplit("/", 1)[-1]
    basename = _UNSAFE_FILENAME_CHARS.sub("", basename).strip()
    if not basename or basename in {".", ".."}:
        raise HTTPException(status_code=400, detail="File name is required")
    return basename[:255]


async def read_upload_limited(
    file: UploadFile,
    *,
    allowed_extensions: set[str],
    max_bytes: int | None = None,
) -> tuple[bytes, str]:
    """Validate an upload and read at most ``max_bytes`` into memory."""

    size_limit = max_bytes if max_bytes is not None else MAX_UPLOAD_BYTES
    filename = sanitize_upload_filename(file.filename)
    extension = Path(filename).suffix.lower()
    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed extensions: {allowed}",
        )
    if file.size is not None and file.size > size_limit:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds the {size_limit // (1024 * 1024)} MB limit",
        )

    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(READ_CHUNK_BYTES):
        total += len(chunk)
        if total > size_limit:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File exceeds the {size_limit // (1024 * 1024)} MB limit",
            )
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    return b"".join(chunks), filename
