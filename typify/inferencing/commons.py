from typify.preprocessing.symbol_table import DefinitionTable, InstanceTable, ClassTable
from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.module_meta import ModuleMeta

from dataclasses import dataclass

@dataclass
class Context:
	module_meta: ModuleMeta
	libs: dict[str, LibraryMeta]
	sysmodules: dict[str, InstanceTable]

class Builtins:
	lib: LibraryMeta = None
	
	def get_type(type_name: str) -> DefinitionTable | None:
		if Builtins.lib and "builtins" in Builtins.lib.library_table.modules:
			module = Builtins.lib.library_table.modules["builtins"]
			if type_name in module.classes:
				return module.classes[type_name].get_latest_definition()
			return None
		return None


def bind_builtin_lib(lib: LibraryMeta):
	Builtins.lib = lib