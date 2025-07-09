from __future__ import annotations
from dataclasses import dataclass

from typify.preprocessing.symbol_table import (
	Name,
	DefinitionTable,
)

@dataclass(frozen=True)
class TargetEntry:
	definition: DefinitionTable
	namespace_name: Name
	symbol_name: Name = None

@dataclass
class PackGroup:
	groups: list[set[TargetEntry] | PackGroup]
	starred: bool