from src.symbol_table import (
    Table,
	LibraryTable,
    PackageTable,
    ModuleTable,
	InstanceTable
)
from src.preprocessing.symbol_slot_collector import SymbolSlotCollector
from src.preprocessing.module_meta import ModuleMeta
from src.preloading.commons import Builtins
from src.typeutils import TypeUtils

from pathlib import Path

class LibraryMeta:
	def __init__(self, working_directory):
		self.working_directory = Path(working_directory).resolve()
		self.library_table = LibraryTable(self.working_directory.name)
		self.module_object_map: dict[ModuleTable | PackageTable, InstanceTable] = {}
		self.meta_map: dict[ModuleTable, ModuleMeta] = {}
		self.dependency_graph: dict[ModuleMeta, set[ModuleMeta]] = {}
		self.symbols: set[Table] = set()

		self._build()
	
	def _build(self):
		working_is_package = (self.working_directory / "__init__.py").is_file()

		if working_is_package:
			root_package_table = PackageTable(self.working_directory.name)
			self.library_table.add_package(root_package_table)
			package_map = {self.working_directory: root_package_table}
		else:
			package_map = {self.working_directory: self.library_table}

		for path in self.working_directory.rglob("*"):
			if path.is_dir():
				if "__pycache__" in path.parts:
					continue

				has_init = (path / "__init__.py").is_file()
				if has_init:
					package_table = PackageTable(path.name)
					package_map[path] = package_table
					parent_table = package_map.get(path.parent, self.library_table)
					parent_table.add_package(package_table)

			elif path.suffix == ".py":
				package_table = package_map.get(path.parent, self.library_table)
				meta = ModuleMeta.from_source(path, self.library_table)
				package_table.add_module(meta.table)
				self.meta_map[meta.table] = meta
	
	def collect_symbols(self):
		for meta in self.meta_map.values():
			ssc = SymbolSlotCollector(meta)
			ssc.visit(meta.tree)
			self.symbols.update(ssc.symbols)