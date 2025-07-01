from __future__ import annotations
from dataclasses import dataclass

from typify.preprocessing.symbol_table import (
	NameTable,
	DefinitionTable,
)

@dataclass(frozen=True)
class TargetEntry:
    name: NameTable
    definition: DefinitionTable

@dataclass
class PackGroup:
	groups: list[set[TargetEntry] | PackGroup]
	starred: bool

class UnpackingUtils:
      
	@staticmethod
	def pretty_print_packgroup(pg: PackGroup, indent: int = 0):
		indent_str = "  " * indent
		star = "Starred " if pg.starred else ""
		print(f"{indent_str}{star}PackGroup:")
		for group in pg.groups:
			if isinstance(group, PackGroup):
				UnpackingUtils.pretty_print_packgroup(group, indent + 1)
			else:
				print(f"{indent_str}  Group:")
				for entry in group:
					print(f"{indent_str}    - {entry.name.key} (line {entry.definition.position[0]})")