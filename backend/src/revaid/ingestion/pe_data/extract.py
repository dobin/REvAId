"""Turn (function, assembly) rows plus a PE image into data items and references."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from revaid.db.enums import DataItemKind
from revaid.ingestion.pe_data.asm_refs import iter_asm_literals
from revaid.ingestion.pe_data.classify import PeLike, classify_data


@dataclass(frozen=True, slots=True)
class ExtractedItem:
    address: int
    rva: int
    section: str
    kind: DataItemKind
    size: int
    value_text: str | None
    target_address: int | None
    preview_hex: str | None
    is_writable: bool


@dataclass(frozen=True, slots=True)
class ExtractedRef:
    function_id: int
    item_address: int
    instruction_address: int
    instruction_text: str


@dataclass(slots=True)
class ExtractionResult:
    items: dict[int, ExtractedItem] = field(default_factory=dict)
    refs: list[ExtractedRef] = field(default_factory=list)
    truncated: bool = False


def extract_data_references(
    image: PeLike,
    functions: Iterable[tuple[int, int, str | None]],
    *,
    analysis_image_base: int | None,
    preview_bytes: int,
    max_string_bytes: int,
    max_items: int,
) -> ExtractionResult:
    """Extract data items/references from ``(function_id, address, assembly)`` rows.

    Addresses use the export's address space (``analysis_image_base``); the PE
    is addressed by RVA. Only non-executable sections are considered.
    """
    base = analysis_image_base if analysis_image_base is not None else image.image_base
    result = ExtractionResult()
    seen_refs: set[tuple[int, int, int]] = set()
    # RVA -> item address cache so each location is classified once.
    rejected: set[int] = set()

    for function_id, _address, assembly in functions:
        if not assembly:
            continue
        for literal in iter_asm_literals(assembly):
            address = literal.value
            if address in rejected:
                continue
            item = result.items.get(address)
            if item is None:
                rva = address - base
                section = image.section_at(rva) if 0 <= rva < image.size_of_image else None
                if section is None or section.executable:
                    rejected.add(address)
                    continue
                if len(result.items) >= max_items:
                    result.truncated = True
                    continue
                classified = classify_data(
                    image, rva, preview_bytes=preview_bytes, max_string_bytes=max_string_bytes
                )
                target = classified.target_address
                item = ExtractedItem(
                    address=address,
                    rva=rva,
                    section=section.name,
                    kind=classified.kind,
                    size=classified.size,
                    value_text=classified.value_text,
                    target_address=(target - image.image_base + base) if target else None,
                    preview_hex=classified.preview_hex,
                    is_writable=section.writable,
                )
                result.items[address] = item
            key = (function_id, address, literal.instruction_address)
            if key in seen_refs:
                continue
            seen_refs.add(key)
            result.refs.append(
                ExtractedRef(
                    function_id=function_id,
                    item_address=address,
                    instruction_address=literal.instruction_address,
                    instruction_text=literal.instruction_text,
                )
            )
    return result
