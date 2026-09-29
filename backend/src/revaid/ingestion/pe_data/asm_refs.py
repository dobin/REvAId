"""Find literal address operands in exported assembly text.

Both the Ghidra script and Kuna emit ``<hex address>  <MNEMONIC> <operands>``
per line. Only the instruction address, its text and every ``0x...`` literal
are extracted here; deciding whether a literal is a data address is left to
the caller (it must fall inside a PE data section).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

_LINE_RE = re.compile(r"^([0-9a-fA-F]+)\s{2,}(\S.*)$")
_HEX_LITERAL_RE = re.compile(r"\b0x([0-9a-fA-F]+)\b")

#: Smallest literal considered; filters displacements and small constants
#: cheaply before any PE lookup.
MIN_ADDRESS_LITERAL = 0x1000
MAX_INSTRUCTION_TEXT = 200


@dataclass(frozen=True, slots=True)
class AsmLiteral:
    instruction_address: int
    instruction_text: str
    value: int


def iter_asm_literals(assembly: str) -> Iterator[AsmLiteral]:
    """Yield each candidate hex literal in ``assembly`` with its instruction."""
    for line in assembly.splitlines():
        match = _LINE_RE.match(line.strip())
        if match is None:
            continue
        instruction_address = int(match.group(1), 16)
        text = match.group(2)
        seen: set[int] = set()
        for literal in _HEX_LITERAL_RE.finditer(text):
            value = int(literal.group(1), 16)
            if value < MIN_ADDRESS_LITERAL or value in seen:
                continue
            seen.add(value)
            yield AsmLiteral(
                instruction_address=instruction_address,
                instruction_text=text[:MAX_INSTRUCTION_TEXT],
                value=value,
            )
