"""Thin read-only wrapper over ``pefile`` for the data-extraction step."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path

import pefile  # type: ignore[import-untyped]

_IMAGE_SCN_MEM_EXECUTE = 0x20000000
_IMAGE_SCN_MEM_WRITE = 0x80000000
_IMAGE_SCN_CNT_CODE = 0x00000020
_PE32_PLUS_MAGIC = 0x20B


@dataclass(frozen=True, slots=True)
class PeSection:
    name: str
    rva: int
    virtual_size: int
    raw_offset: int
    raw_size: int
    executable: bool
    writable: bool

    @property
    def span(self) -> int:
        return max(self.virtual_size, self.raw_size)

    def contains(self, rva: int) -> bool:
        return self.rva <= rva < self.rva + self.span


class PeImage:
    """Parsed PE: sections, import slots, relocations and raw byte reads."""

    def __init__(self, path: Path) -> None:
        pe = pefile.PE(str(path), fast_load=True)
        with contextlib.suppress(Exception):
            # Damaged directories must not prevent section-based extraction.
            pe.parse_data_directories(
                directories=[
                    pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                    pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
                    pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_BASERELOC"],
                ]
            )
        self._data: bytes = bytes(pe.__data__)
        self.image_base: int = int(pe.OPTIONAL_HEADER.ImageBase)
        self.size_of_image: int = int(pe.OPTIONAL_HEADER.SizeOfImage)
        self.pointer_size: int = 8 if pe.OPTIONAL_HEADER.Magic == _PE32_PLUS_MAGIC else 4
        self.sections: list[PeSection] = [
            PeSection(
                name=s.Name.rstrip(b"\x00").decode("ascii", errors="replace"),
                rva=int(s.VirtualAddress),
                virtual_size=int(s.Misc_VirtualSize),
                raw_offset=int(s.PointerToRawData),
                raw_size=int(s.SizeOfRawData),
                executable=bool(s.Characteristics & (_IMAGE_SCN_MEM_EXECUTE | _IMAGE_SCN_CNT_CODE)),
                writable=bool(s.Characteristics & _IMAGE_SCN_MEM_WRITE),
            )
            for s in pe.sections
        ]
        # Precomputed (start, end, section) so lookups avoid property calls.
        self._spans: list[tuple[int, int, PeSection]] = [
            (s.rva, s.rva + s.span, s) for s in self.sections
        ]
        self.import_slots: dict[int, str] = {}
        for attr in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT"):
            for entry in getattr(pe, attr, []) or []:
                dll = _decode(entry.dll)
                for imp in entry.imports:
                    if not imp.address:
                        continue
                    slot_rva = int(imp.address) - self.image_base
                    label = _decode(imp.name) if imp.name else f"#{imp.ordinal}"
                    self.import_slots[slot_rva] = f"{dll}::{label}"
        self.relocation_rvas: set[int] = set()
        for block in getattr(pe, "DIRECTORY_ENTRY_BASERELOC", []) or []:
            for reloc in block.entries:
                if reloc.type in (
                    pefile.RELOCATION_TYPE["IMAGE_REL_BASED_DIR64"],
                    pefile.RELOCATION_TYPE["IMAGE_REL_BASED_HIGHLOW"],
                ):
                    self.relocation_rvas.add(int(reloc.rva))
        pe.close()

    def section_at(self, rva: int) -> PeSection | None:
        for start, end, section in self._spans:
            if start <= rva < end:
                return section
        return None

    def read(self, rva: int, length: int) -> bytes | None:
        """Initialized file bytes at ``rva`` (clipped), or ``None`` if none exist.

        ``None`` means the location has no file backing (e.g. .bss).
        """
        section = self.section_at(rva)
        if section is None:
            return None
        delta = rva - section.rva
        available = section.raw_size - delta
        if available <= 0:
            return None
        start = section.raw_offset + delta
        return self._data[start : start + min(length, available)]


def _decode(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.decode("ascii", errors="replace")
