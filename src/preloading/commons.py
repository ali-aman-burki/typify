from src.typeutils import TypeExpr
from src.symbol_table import ModuleTable, ClassTable
from src.preloading.module_utils import ModuleUtils

builtins_m = ModuleTable("builtins")
typing_m =  ModuleTable("typing")

class Builtins:
	TypeClass = ModuleUtils.add(builtins_m, ClassTable("type"))
	ModuleClass = ModuleUtils.add(builtins_m, ClassTable("module"), TypeClass)
	FunctionClass = ModuleUtils.add(builtins_m, ClassTable("function"), TypeClass)

class Typing:
	GenericClass = ModuleUtils.add(typing_m, ClassTable("Generic"), Builtins.TypeClass)
	TypeVarClass = ModuleUtils.add(typing_m, ClassTable("TypeVar"), Builtins.TypeClass)
	OptionalClass = ModuleUtils.add(typing_m, ClassTable("Optional"), Builtins.TypeClass)
	NewTypeClass = ModuleUtils.add(typing_m, ClassTable("NewType"), Builtins.TypeClass)
	LiteralClass = ModuleUtils.add(typing_m, ClassTable("Literal"), Builtins.TypeClass)
	ListClass = ModuleUtils.add(typing_m, ClassTable("List"), Builtins.TypeClass)
	SetClass = ModuleUtils.add(typing_m, ClassTable("Set"), Builtins.TypeClass)
	DictClass = ModuleUtils.add(typing_m, ClassTable("Dict"), Builtins.TypeClass)
	TupleCLass = ModuleUtils.add(typing_m, ClassTable("Tuple"), Builtins.TypeClass)
	UnionClass = ModuleUtils.add(typing_m, ClassTable("Union"), Builtins.TypeClass)
	CallableClass = ModuleUtils.add(typing_m, ClassTable("Callable"), Builtins.TypeClass)
	TypeClass = ModuleUtils.add(typing_m, ClassTable("Type"), Builtins.TypeClass)
	AnyClass = ModuleUtils.add(typing_m, ClassTable("Any"), Builtins.TypeClass)

	AnyType = TypeExpr(AnyClass, [])