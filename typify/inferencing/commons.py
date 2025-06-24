from typify.preprocessing.symbol_table import ClassTable
from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.symbol_table import (
    InstanceTable,
    ModuleTable,
)

class Builtins:
	ModuleClass: InstanceTable = None
	TypeClass: InstanceTable = None
	FunctionClass: InstanceTable = None

class Typing:
	AnyClass: InstanceTable = None
	ListClass: InstanceTable = None

def _bind_builtins(lib: LibraryMeta, namespace: InstanceTable, symbol: ModuleTable):
	if not Builtins.ModuleClass or Builtins.ModuleClass.is_null():
		if lib.key == "builtinlib" and symbol.key == "builtins":
			ModuleClassName = namespace.names.get("module", None)
			if ModuleClassName:
				points_to = ModuleClassName.get_latest_definition().points_to
				for pt in points_to:
					Builtins.ModuleClass = pt
					break

	if lib.key == "builtinlib" and symbol.key == "builtins":
		Builtins.TypeClass = namespace.names.get("type", None)
	if lib.key == "builtinlib" and symbol.key == "builtins":
		Builtins.FunctionClass = namespace.names.get("function", None)

def _bind_typing(lib: LibraryMeta, namespace: InstanceTable, symbol: ModuleTable):
	if lib.key == "stdlib" and symbol.key == "typing":
		Typing.AnyClass = namespace.names.get("Any", None)
	if lib.key == "stdlib" and symbol.key == "typing":
		Typing.ListClass = namespace.names.get("List", None)

def bind(lib: LibraryMeta, namespace: InstanceTable, symbol: ModuleTable):
	_bind_builtins(lib, namespace, symbol)
	_bind_typing(lib, namespace, symbol)
