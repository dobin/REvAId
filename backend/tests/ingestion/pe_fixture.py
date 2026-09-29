"""Build a tiny synthetic PE32+ file for data-extraction tests.

Layout (image base 0x140000000):
  .text   RVA 0x1000  (executable)
  .rdata  RVA 0x2000  strings + IAT slot + pointer
  .data   RVA 0x3000  writable; 0x100 raw bytes then uninitialized tail
"""

from __future__ import annotations

import struct
from pathlib import Path

IMAGE_BASE = 0x140000000
TEXT_RVA, RDATA_RVA, DATA_RVA = 0x1000, 0x2000, 0x3000
STRING_RVA = RDATA_RVA + 0x00  # "hello world\0"
WSTRING_RVA = RDATA_RVA + 0x20  # L"wide text\0"
POINTER_RVA = RDATA_RVA + 0x60  # pointer -> STRING
GLOBAL_RVA = DATA_RVA + 0x00  # 8 bytes of non-string data
BSS_RVA = DATA_RVA + 0x200  # beyond raw size -> uninitialized
_ALIGN = 0x200


def build_pe(path: Path) -> Path:
    text = b"\xc3" + b"\x00" * (_ALIGN - 1)
    rdata = bytearray(_ALIGN)
    rdata[0x00 : 0x00 + 12] = b"hello world\x00"
    rdata[0x20 : 0x20 + 20] = "wide text".encode("utf-16le") + b"\x00\x00"
    rdata[0x60:0x68] = struct.pack("<Q", IMAGE_BASE + STRING_RVA)
    data = bytearray(_ALIGN)
    data[0:8] = b"\x01\x02\x03\x04\x05\x06\x07\x08"

    headers_size = 0x200
    dos = bytearray(0x40)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, 0x40)
    pe_sig = b"PE\x00\x00"
    optional_size = 0xF0
    coff = struct.pack("<HHIIIHH", 0x8664, 3, 0, 0, 0, optional_size, 0x22)
    opt = bytearray(optional_size)
    struct.pack_into("<H", opt, 0, 0x20B)  # PE32+
    struct.pack_into("<I", opt, 16, TEXT_RVA)  # entry point
    struct.pack_into("<Q", opt, 24, IMAGE_BASE)
    struct.pack_into("<II", opt, 32, 0x1000, _ALIGN)  # section/file alignment
    struct.pack_into("<I", opt, 56, 0x4000)  # SizeOfImage
    struct.pack_into("<I", opt, 60, headers_size)
    struct.pack_into("<H", opt, 68, 3)  # subsystem
    struct.pack_into("<I", opt, 108, 16)  # NumberOfRvaAndSizes

    def section(
        name: bytes, vsize: int, rva: int, raw_size: int, raw_ptr: int, flags: int
    ) -> bytes:
        return struct.pack("<8sIIIIIIHHI", name, vsize, rva, raw_size, raw_ptr, 0, 0, 0, 0, flags)

    sections = (
        section(b".text", 0x200, TEXT_RVA, _ALIGN, 0x200, 0x60000020)
        + section(b".rdata", 0x200, RDATA_RVA, _ALIGN, 0x400, 0x40000040)
        + section(b".data", 0x400, DATA_RVA, _ALIGN, 0x600, 0xC0000040)
    )
    header = bytes(dos) + pe_sig + coff + bytes(opt) + sections
    header = header.ljust(headers_size, b"\x00")
    path.write_bytes(header + text + bytes(rdata) + bytes(data))
    return path
