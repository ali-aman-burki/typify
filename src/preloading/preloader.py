from src.symbol_table import LibraryTable, ModuleTable, ClassTable, Table
from src.preloading.module_utils import ModuleUtils
from src.typeutils import TypeUtils
from pathlib import Path

class PreloadedLibs:

	def __init__(self, env_meta: dict[str, list[str] | str]):
		builtins_path = env_meta["builtins"]
		pystd_path = env_meta["stdlib"]
		site_paths = env_meta["site_packages"]
		user_site_paths = env_meta["user_site_packages"]

		self.builtin_lib: LibraryTable = LibraryTable("builtin_lib")
		self.pystd_lib: LibraryTable = LibraryTable("pystd_lib")
		self.site_libs: dict[Path, LibraryTable] = {}
		self.user_site_libs: dict[Path, LibraryTable] = {}

		self._pre_init()

		self._init_builtin_lib(builtins_path)
		self._init_pystd_lib(pystd_path)
		self._init_site_libs(site_paths)
		self._init_user_site_libs(user_site_paths)
	
	def _pre_init(self):
		m_builtins = self.builtin_lib.add_module(ModuleTable("builtins"))
		m_typing = self.pystd_lib.add_module(ModuleTable("typing"))

		type_class = ModuleUtils.add(m_builtins, ClassTable("type"))
		object_class = ModuleUtils.add(m_builtins, ClassTable("object"))
		
		ModuleUtils.add(m_typing, ClassTable("Generic"), type_class).bases.append(object_class)
		ModuleUtils.add(m_typing, ClassTable("TypeVar"), type_class).bases.append(object_class)
		ModuleUtils.add(m_typing, ClassTable("Optional"), type_class).bases.append(object_class)
		ModuleUtils.add(m_typing, ClassTable("NewType"), type_class).bases.append(object_class)
		ModuleUtils.add(m_typing, ClassTable("Literal"), type_class).bases.append(object_class)
		ModuleUtils.add(m_typing, ClassTable("List"), type_class).bases.append(object_class)
		ModuleUtils.add(m_typing, ClassTable("Set"), type_class).bases.append(object_class)
		ModuleUtils.add(m_typing, ClassTable("Dict"), type_class).bases.append(object_class)
		ModuleUtils.add(m_typing, ClassTable("Tuple"), type_class).bases.append(object_class)
		ModuleUtils.add(m_typing, ClassTable("Union"), type_class).bases.append(object_class)
		ModuleUtils.add(m_typing, ClassTable("Callable"), type_class).bases.append(object_class)
		ModuleUtils.add(m_typing, ClassTable("Type"), type_class).bases.append(object_class)
		ModuleUtils.add(m_typing, ClassTable("Any"), type_class).bases.append(object_class)

	def _init_builtin_lib(self, builtins_path: Path):
		m_builtins = self.builtin_lib.modules["builtins"]
		object_class = m_builtins.classes["object"]
		type_class = m_builtins.classes["type"]

		ModuleUtils.add(m_builtins, ClassTable("function"), type_class).bases.append(object_class)
		ModuleUtils.add(m_builtins, ClassTable("module"), type_class).bases.append(object_class)
		ModuleUtils.add(m_builtins, ClassTable("list"), type_class).bases.append(object_class)
		ModuleUtils.add(m_builtins, ClassTable("set"), type_class).bases.append(object_class)
		ModuleUtils.add(m_builtins, ClassTable("dict"), type_class).bases.append(object_class)
		ModuleUtils.add(m_builtins, ClassTable("tuple"), type_class).bases.append(object_class)
		ModuleUtils.add(m_builtins, ClassTable("str"), type_class).bases.append(object_class)
		ModuleUtils.add(m_builtins, ClassTable("int"), type_class).bases.append(object_class)
		ModuleUtils.add(m_builtins, ClassTable("float"), type_class).bases.append(object_class)
		ModuleUtils.add(m_builtins, ClassTable("bool"), type_class).bases.append(object_class)
		ModuleUtils.add(m_builtins, ClassTable("NoneType"), type_class).bases.append(object_class)
		ModuleUtils.add(m_builtins, ClassTable("bytes"), type_class).bases.append(object_class)
		ModuleUtils.add(m_builtins, ClassTable("complex"), type_class).bases.append(object_class)

		bobject = TypeUtils.create_instance(m_builtins.classes["module"], [])
		Table.transfer_content(m_builtins, bobject)
		self.builtin_lib.module_object_map[m_builtins] = bobject

	def _init_pystd_lib(self, pystd_path: Path): 
		m_builtins = self.builtin_lib.modules["builtins"]
		m_typing = self.pystd_lib.modules["typing"]

		tobject = TypeUtils.create_instance(m_builtins.classes["module"], [])
		Table.transfer_content(m_typing, tobject)
		self.pystd_lib.module_object_map[m_typing] = tobject

	def _init_site_libs(self, site_paths: list[Path]): pass
	def _init_user_site_libs(self, user_site_paths: list[Path]): pass