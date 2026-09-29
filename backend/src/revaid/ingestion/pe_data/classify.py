"""Classify the bytes at a PE data location."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from revaid.db.enums import DataItemKind
from revaid.ingestion.pe_data.pe_image import PeSection

_MIN_STRING_CHARS = 3
_PRINTABLE_WHITESPACE = {0x09, 0x0A, 0x0D}


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
    chars = bytearray()
    for index, byte in enumerate(data[:max_chars]):
        if byte == 0:
            if len(chars) >= _MIN_STRING_CHARS:
                return chars.decode("ascii"), index + 1
            return None
        if not _is_printable(byte):
            return None
        chars.append(byte)
    if len(chars) == max_chars and len(chars) >= _MIN_STRING_CHARS:
        return chars.decode("ascii"), len(chars)  # cut off at the limit
    return None


def read_utf16(data: bytes, max_chars: int) -> tuple[str, int] | None:
    """Return ``(text, size_with_nul)`` for a printable UTF-16LE (ASCII range) string."""
    chars: list[str] = []
    limit = min(len(data) - 1, max_chars * 2)
    for index in range(0, limit, 2):
        low, high = data[index], data[index + 1]
        if low == 0 and high == 0:
            if len(chars) >= _MIN_STRING_CHARS:
                return "".join(chars), index + 2
            return None
        if high != 0 or not _is_printable(low):
            return None
        chars.append(chr(low))
    if len(chars) == max_chars and len(chars) >= _MIN_STRING_CHARS:
        return "".join(chars), len(chars) * 2  # cut off at the limit
    return None


def _string_at(image: PeLike, rva: int, max_bytes: int) -> tuple[DataItemKind, str, int] | None:
    """Read a string, cut off at ``max_bytes`` bytes of its stored representation."""
    data = image.read(rva, max_bytes + 2)
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

    head = image.read(rva, max(preview_bytes, image.pointer_size))
    if head is None:
        return ClassifiedData(kind="uninitialized", size=0)
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

    text = _string_at(image, rva, max_string_bytes)
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
