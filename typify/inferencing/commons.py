from typify.preprocessing.symbol_table import ClassTable
from typify.preprocessing.library_meta import LibraryMeta

def _safe_get(func):
	try: return func()
	except Exception as e: print(f"[bind error] missing necessary type '{func.__code__.co_consts[-1]}'"); return None

class Builtins:
	ModuleClass: ClassTable = None
	TypeClass: ClassTable = None
	FunctionClass: ClassTable = None

class Typing:
	AnyClass: ClassTable = None
	ListClass: ClassTable = None

def _bind_builtins(libs: dict[str, LibraryMeta]):
	Builtins.ModuleClass = _safe_get(lambda: libs["builtinlib"].library_table.modules["builtins"].classes["module"])
	Builtins.TypeClass = _safe_get(lambda: libs["builtinlib"].library_table.modules["builtins"].classes["type"])
	Builtins.FunctionClass = _safe_get(lambda: libs["builtinlib"].library_table.modules["builtins"].classes["function"])

def _bind_typing(libs: dict[str, LibraryMeta]):
	Typing.AnyClass = _safe_get(lambda: libs["stdlib"].library_table.modules["typing"].classes["Any"])
	Typing.ListClass = _safe_get(lambda: libs["stdlib"].library_table.modules["typing"].classes["List"])

def bind(libs: dict[str, LibraryMeta]):
	_bind_builtins(libs)
	_bind_typing(libs)