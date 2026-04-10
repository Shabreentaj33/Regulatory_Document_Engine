"""
Document Processor
──────────────────
Handles PDF text extraction, semantic chunking, and section detection
for regulatory / clinical documents.
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from backend.config import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    REQUIRED_SECTIONS,
    SECTION_ALIASES,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Normalise whitespace and remove non-printable characters."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\x20-\x7E\n]", " ", text)
    return text.strip()


def _words(text: str) -> list[str]:
    return text.split()


# ─────────────────────────────────────────────────────────────────────────────
# DocumentProcessor
# ─────────────────────────────────────────────────────────────────────────────

class DocumentProcessor:
    """Extract, chunk and classify regulatory PDF documents."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_text_from_pdf(self, file_path: str | Path) -> str:
        """Return the full plain-text content of a PDF file."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        full_text: list[str] = []
        with fitz.open(str(file_path)) as doc:
            for page_num, page in enumerate(doc, start=1):
                page_text = page.get_text("text")
                if page_text.strip():
                    full_text.append(f"\n[Page {page_num}]\n{page_text}")

        raw = "\n".join(full_text)
        return _clean_text(raw)

    # ------------------------------------------------------------------

    def semantic_chunking(
        self,
        text: str,
        chunk_size: int = CHUNK_SIZE,
        overlap: int = CHUNK_OVERLAP,
    ) -> list[str]:
        """
        Split *text* into overlapping word-level chunks.

        Paragraph boundaries are respected where possible so that chunks
        are more semantically coherent.
        """
        if not text.strip():
            return []

        # Split into paragraphs first, then flatten to word list
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        word_buffer: list[str] = []
        for para in paragraphs:
            word_buffer.extend(_words(para))
            word_buffer.append("\n")  # preserve paragraph marker

        words = word_buffer
        chunks: list[str] = []
        start = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_words = words[start:end]
            chunk = " ".join(w for w in chunk_words if w != "\n").strip()
            if chunk:
                chunks.append(chunk)
            start += chunk_size - overlap

        logger.debug("Created %d chunks from %d words", len(chunks), len(words))
        return chunks

    # ------------------------------------------------------------------
    
    def detect_sections(self, text: str) -> dict[str, Any]:
        """
        Identify standard regulatory sections within *text*.

        Returns a dict mapping canonical section names to their extracted
        content (up to ~600 words) plus a boolean *found* flag.
        """
        sections: dict[str, Any] = {}
        text_lower = text.lower()

        for canonical in REQUIRED_SECTIONS:
            aliases = SECTION_ALIASES.get(canonical, [canonical])
            section_content: str | None = None

            for alias in [canonical] + aliases:
                # Build a pattern that matches a heading-like occurrence
                pattern = rf"(?i)(?:^|\n)\s*{re.escape(alias)}[:\s\n]"
                match = re.search(pattern, text, re.MULTILINE)
                if match:
                    start_idx = match.end()
                    # Grab text until the next heading or 600 words
                    remaining = text[start_idx:]
                    next_heading = re.search(
                        r"\n\s*[A-Z][A-Za-z\s]{3,40}[:\n]", remaining
                    )
                    end_idx = next_heading.start() if next_heading else len(remaining)
                    raw_content = remaining[:end_idx].strip()
                    words = _words(raw_content)
                    section_content = " ".join(words[:600])
                    break

            sections[canonical] = {
                "found": section_content is not None,
                "content": section_content or "",
            }

        return sections

    # ------------------------------------------------------------------

    def process_document(self, file_path: str | Path) -> dict[str, Any]:
        """
        Full pipeline: extract → chunk → detect sections.

        Returns
        -------
        dict with keys: ``text``, ``chunks``, ``sections``
        """
        file_path = Path(file_path)
        logger.info("Processing document: %s", file_path.name)

        text = self.extract_text_from_pdf(file_path)
        chunks = self.semantic_chunking(text)
        sections = self.detect_sections(text)

        return {
            "text": text,
            "chunks": chunks,
            "sections": sections,
            "filename": file_path.name,
            "char_count": len(text),
            "chunk_count": len(chunks),
        }