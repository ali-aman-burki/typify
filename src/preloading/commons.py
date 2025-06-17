from src.typeutils import TypeExpr
from src.symbol_table import LibraryTable, ModuleTable, ClassTable
from src.preloading.preloader import PreloadedLibs

from pathlib import Path

preloaded_libs = None

builtin_lib: LibraryTable = None
pystd_lib: LibraryTable = None
site_libs: dict[Path, LibraryTable] = None
user_site_libs: dict[Path, LibraryTable] = None

builtins_m: ModuleTable = None
typing_m: ModuleTable =  None

TypeClass: ClassTable = None
ModuleClass: ClassTable = None
FunctionClass: ClassTable = None

AnyType: TypeExpr = None

def bind(pl: PreloadedLibs):
	global preloaded_libs
	global builtin_lib, pystd_lib, site_libs, user_site_libs
	global builtins_m, typing_m
	global TypeClass, ModuleClass, FunctionClass
	global AnyType
	
	preloaded_libs = pl

	builtin_lib = preloaded_libs.builtin_lib
	pystd_lib = preloaded_libs.pystd_lib
	site_libs = preloaded_libs.site_libs
	user_site_libs = preloaded_libs.user_site_libs

	builtins_m = builtin_lib.modules["builtins"]
	typing_m =  pystd_lib.modules["typing"]

	TypeClass = builtins_m.classes["type"]
	ModuleClass = builtins_m.classes["module"]
	FunctionClass = builtins_m.classes["function"]

	AnyType = TypeExpr(typing_m.classes["Any"], [])