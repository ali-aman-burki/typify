from __future__ import annotations
from dataclasses import dataclass

from typify.preprocessing.symbol_table import (
	NameTable,
	DefinitionTable,
)

@dataclass(frozen=True)
class TargetEntry:
	definition: DefinitionTable
	namespace_name: NameTable
	symbol_name: NameTable = None

@dataclass
class PackGroup:
	groups: list[set[TargetEntry] | PackGroup]
	starred: bool