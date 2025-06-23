from typify.preprocessing.symbol_table import ClassTable
from typify.preprocessing.library_meta import LibraryMeta

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

class Flag:
	builtins_initialized = False
	typing_initialized = False

def _bind_builtins(libs: dict[str, LibraryMeta]):
	if Flag.builtins_initialized:
		return

	if not Builtins.ModuleClass:
		Builtins.ModuleClass = _safe_get(lambda: libs["builtinlib"].library_table.modules["builtins"].classes["module"])
	if not Builtins.TypeClass:
		Builtins.TypeClass = _safe_get(lambda: libs["builtinlib"].library_table.modules["builtins"].classes["type"])
	if not Builtins.FunctionClass:
		Builtins.FunctionClass = _safe_get(lambda: libs["builtinlib"].library_table.modules["builtins"].classes["function"])

	Flag.builtins_initialized = all([
		Builtins.ModuleClass,
		Builtins.TypeClass,
		Builtins.FunctionClass
	])

def _bind_typing(libs: dict[str, LibraryMeta]):
	if Flag.typing_initialized:
		return

	if not Typing.AnyClass:
		Typing.AnyClass = _safe_get(lambda: libs["stdlib"].library_table.modules["typing"].classes["Any"])
	if not Typing.ListClass:
		Typing.ListClass = _safe_get(lambda: libs["stdlib"].library_table.modules["typing"].classes["List"])

	Flag.typing_initialized = all([
		Typing.AnyClass,
		Typing.ListClass
	])

def bind(libs: dict[str, LibraryMeta]):
	_bind_builtins(libs)
	_bind_typing(libs)
