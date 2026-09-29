"""Classify the bytes at a PE data location."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from revaid.db.enums import DataItemKind
from revaid.ingestion.pe_data.pe_image import PeSection

_MIN_STRING_CHARS = 3
_PRINTABLE_WHITESPACE = {0x09, 0x0A, 0x0D}
_ASCII_RUN = re.compile(rb"[\t\n\r\x20-\x7e]*")
_UTF16_RUN = re.compile(rb"(?:[\t\n\r\x20-\x7e]\x00)*")


class PeLike(Protocol):
    image_base: int
    size_of_image: int
    pointer_size: int
    import_slots: dict[int, str]
    relocation_rvas: set[int]

    def section_at(self, rva: int) -> PeSection | None: ...

    def read(self, rva: int, length: int) -> bytes | None: ...


@dataclass(frozen=True, slots=True)
class ClassifiedData:
    kind: DataItemKind
    size: int
    value_text: str | None = None
    target_address: int | None = None
    preview_hex: str | None = None


def _is_printable(byte: int) -> bool:
    return 0x20 <= byte <= 0x7E or byte in _PRINTABLE_WHITESPACE


def read_ascii(data: bytes, max_chars: int) -> tuple[str, int] | None:
    """Return ``(text, size)`` for a printable string, cut off at ``max_chars``."""
    window = data[:max_chars]
    run = _ASCII_RUN.match(window).end()  # type: ignore[union-attr]
    if run < len(window):
        if window[run] == 0 and run >= _MIN_STRING_CHARS:
            return window[:run].decode("ascii"), run + 1
        return None
    if run == max_chars and run >= _MIN_STRING_CHARS:
        return window.decode("ascii"), run  # cut off at the limit
    return None


def read_utf16(data: bytes, max_chars: int) -> tuple[str, int] | None:
    """Return ``(text, size_with_nul)`` for a printable UTF-16LE (ASCII range) string."""
    limit = min(len(data) - 1, max_chars * 2)
    if limit <= 0:
        return None
    pairs = (limit + 1) // 2
    window = data[: pairs * 2]
    end = _UTF16_RUN.match(window).end()  # type: ignore[union-attr]
    chars = end // 2
    if chars < pairs:
        if window[end] == 0 and window[end + 1] == 0 and chars >= _MIN_STRING_CHARS:
            return window[:end:2].decode("ascii"), end + 2
        return None
    if chars == max_chars and chars >= _MIN_STRING_CHARS:
        return window[:end:2].decode("ascii"), chars * 2  # cut off at the limit
    return None


def _string_at(
    image: PeLike, rva: int, max_bytes: int, data: bytes | None = None
) -> tuple[DataItemKind, str, int] | None:
    """Read a string, cut off at ``max_bytes`` bytes of its stored representation."""
    data = image.read(rva, max_bytes + 2) if data is None else data[: max_bytes + 2]
    if not data:
        return None
    ascii_string = read_ascii(data, max_bytes)
    if ascii_string is not None:
        return "string", ascii_string[0], ascii_string[1]
    wide = read_utf16(data, max_bytes // 2)
    if wide is not None:
        return "wstring", wide[0], wide[1]
    return None


def classify_data(
    image: PeLike,
    rva: int,
    *,
    preview_bytes: int,
    max_string_bytes: int,
) -> ClassifiedData:
    """Classify the location at ``rva``; the caller guarantees it is in a section."""
    slot = image.import_slots.get(rva)
    if slot is not None:
        return ClassifiedData(kind="import", size=image.pointer_size, value_text=slot)

    head_len = max(preview_bytes, image.pointer_size)
    # One read serves the preview, pointer and string checks.
    blob = image.read(rva, max(head_len, max_string_bytes + 2))
    if blob is None:
        return ClassifiedData(kind="uninitialized", size=0)
    head = blob[:head_len]
    preview = head[:preview_bytes].hex()

    pointer_size = image.pointer_size
    pointer_target: int | None = None
    if len(head) >= pointer_size:
        value = int.from_bytes(head[:pointer_size], "little")
        target_rva = value - image.image_base
        if 0 <= target_rva < image.size_of_image and image.section_at(target_rva) is not None:
            pointer_target = value
            if rva in image.relocation_rvas:
                return _pointer(image, pointer_target, target_rva, preview, max_string_bytes)

    text = _string_at(image, rva, max_string_bytes, blob)
    if text is not None:
        kind, value_text, size = text
        return ClassifiedData(kind=kind, size=size, value_text=value_text)

    if pointer_target is not None:
        return _pointer(
            image, pointer_target, pointer_target - image.image_base, preview, max_string_bytes
        )
    return ClassifiedData(kind="bytes", size=len(head), preview_hex=preview)


def _pointer(
    image: PeLike, target: int, target_rva: int, preview: str, max_string_bytes: int
) -> ClassifiedData:
    pointed = _string_at(image, target_rva, max_string_bytes)
    return ClassifiedData(
        kind="pointer",
        size=image.pointer_size,
        value_text=pointed[1] if pointed is not None else None,
        target_address=target,
        preview_hex=preview,
    )
