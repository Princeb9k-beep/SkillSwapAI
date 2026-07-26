"""Extract plain text from an uploaded file for AI critique.

Supports text/code files (decoded directly) and PDFs (via pypdf). Images and
other binaries aren't supported yet — we raise a clear error the router turns
into a friendly message. Kept dependency-light and defensive: nothing here
should ever crash a request.
"""

from __future__ import annotations

import io
import os

MAX_BYTES = 4 * 1024 * 1024  # 4 MB upload cap
MAX_CHARS = 20000            # matches the ScanRequest text limit

# Extensions we treat as UTF-8 text.
TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".log",
    ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".html", ".htm", ".css",
    ".java", ".go", ".rb", ".c", ".h", ".cpp", ".cc", ".cs", ".sh", ".bash",
    ".yml", ".yaml", ".toml", ".ini", ".rs", ".php", ".sql", ".swift", ".kt",
}


class UnsupportedFile(ValueError):
    """Raised when we can't get text out of the upload."""


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency always present
        raise UnsupportedFile("PDF support isn't available on the server.") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # noqa: BLE001
        raise UnsupportedFile("Couldn't read that PDF — try a text file.") from exc


def extract_text(filename: str, data: bytes) -> str:
    """Return cleaned text from an uploaded file, or raise UnsupportedFile."""
    if not data:
        raise UnsupportedFile("The file is empty.")
    if len(data) > MAX_BYTES:
        raise UnsupportedFile("That file is too large (max 4 MB).")

    ext = os.path.splitext(filename or "")[1].lower()
    if ext == ".pdf":
        text = _extract_pdf(data)
    elif ext in TEXT_EXTS or ext == "":
        text = data.decode("utf-8", errors="replace")
    else:
        raise UnsupportedFile(
            f"Can't read {ext} files yet — upload a PDF or a text/code file, "
            "or paste the content instead."
        )

    text = text.strip()
    if len(text) < 20:
        raise UnsupportedFile("Couldn't find enough readable text in that file.")
    return text[:MAX_CHARS]
