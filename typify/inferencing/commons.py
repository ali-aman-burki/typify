from typify.preprocessing.symbol_table import (
    DefinitionTable, 
    InstanceTable, 
    Table
)
from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.symbol_table import ModuleTable
from typify.preprocessing.libs import RequiredLibs

from dataclasses import dataclass

@dataclass
class Context:
	module_meta: ModuleMeta
	libs: dict[str, LibraryMeta]
	sysmodules: dict[str, InstanceTable]
	symbol_map: dict[Table, InstanceTable]

class Builtins:
	
	@staticmethod
	def module() -> ModuleTable:
		try:
			result = RequiredLibs.preloaded["builtinlib"].library_table.modules["builtins"]
			return result
		except Exception:
			return None
	
	@staticmethod
	def get_type(type_name: str) -> DefinitionTable | None:
		try: 
			result = Builtins.module().classes[type_name].get_latest_definition()
			return result
		except Exception: 
			return None
