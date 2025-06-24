from typify.preprocessing.symbol_table import ClassTable
from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.symbol_table import (
    InstanceTable,
    ModuleTable,
)

def _safe_get(func):
	try: return func()
	except Exception: return None

class Builtins:
	ModuleClass: ClassTable = None
	TypeClass: ClassTable = None
	FunctionClass: ClassTable = None

class Typing:
	AnyClass: ClassTable = None
	ListClass: ClassTable = None

def _bind_builtins(lib: LibraryMeta, namespace: InstanceTable, symbol: ModuleTable):
	if lib.key == "builtinlib" and symbol.key == "builtins":
		Builtins.ModuleClass = namespace.names.get("module", None)
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
