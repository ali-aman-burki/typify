from __future__ import annotations
from dataclasses import dataclass

from typify.preprocessing.symbol_table import (
	Name,
	NameDefinition,
)

@dataclass(frozen=True)
class TargetEntry:
	definition: NameDefinition
	namespace_name: Name
	symbol_name: Name = None

@dataclass
class PackGroup:
	groups: list[set[TargetEntry] | PackGroup]
	starred: bool