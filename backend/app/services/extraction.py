"""Upload validation and text extraction for PDF and TXT documents."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from app.core.errors import EmptyFileError, UnsupportedMediaTypeError

PDF = "application/pdf"
TEXT = "text/plain"
OCTET = "application/octet-stream"

# suffix -> (canonical content type, accepted declared content types)
SUPPORTED_TYPES: dict[str, tuple[str, set[str]]] = {
    ".pdf": (PDF, {PDF, "application/x-pdf", OCTET, ""}),
    ".txt": (TEXT, {TEXT, OCTET, ""}),
}


def file_suffix(filename: str) -> str:
    return Path(filename.replace("\\", "/")).suffix.lower()


def validate_upload(filename: str, content_type: str | None, data: bytes) -> str:
    """Check type and content of an upload; return the canonical content type."""
    suffix = file_suffix(filename)
    declared = (content_type or "").split(";", 1)[0].strip().lower()
    if suffix not in SUPPORTED_TYPES:
        raise UnsupportedMediaTypeError(
            details={"filename": filename, "allowed_suffixes": sorted(SUPPORTED_TYPES)}
        )
    canonical, accepted = SUPPORTED_TYPES[suffix]
    if declared not in accepted:
        raise UnsupportedMediaTypeError(
            f"Content type {declared!r} does not match a {suffix} file",
            details={"filename": filename, "content_type": declared},
        )
    if not data:
        raise EmptyFileError(details={"filename": filename})
    if canonical == PDF and not data.lstrip()[:5].startswith(b"%PDF"):
        raise UnsupportedMediaTypeError(
            "File content is not a PDF", details={"filename": filename}
        )
    return canonical


def extract_text(path: Path, content_type: str | None = None) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf" or (content_type and "pdf" in content_type):
        return _extract_pdf(path)
    if suffix in {".txt", ".text", ".md"} or (
        content_type and ("text" in content_type or "plain" in content_type)
    ):
        return path.read_text(encoding="utf-8", errors="replace")
    # Fallback: try as text
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Unsupported document type: {path.name}") from exc


def _extract_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
    return "\n\n".join(parts)
