"""Opportunistic PE data-reference extraction for raw-binary imports.

Literal addresses in stored function assembly are resolved against the PE's
non-executable sections (``.data``, ``.rdata``, ...). The result is a set of
data items plus function -> data references. Computed or indirect addresses
are not discovered; every reference is tagged ``source='asm-parse'``.
"""
