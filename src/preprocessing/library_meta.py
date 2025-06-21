from src.symbol_table import (
    Table,
	LibraryTable,
    PackageTable,
    ModuleTable,
	InstanceTable
)
from src.preprocessing.module_meta import ModuleMeta

from pathlib import Path

class LibraryMeta:
	def __init__(self, src: Path):
		self.src = Path(src).resolve()
		self.library_table = LibraryTable(self.src.name)
		self.module_object_map: dict[ModuleTable | PackageTable, InstanceTable] = {}
		self.meta_map: dict[ModuleTable, ModuleMeta] = {}
		self.dependency_graph: dict[ModuleMeta, set[ModuleMeta]] = {}
		self.fqn_map: dict[str, list[Table]] = {}

		self._build()
	
	def _build(self):
		working_is_package = (self.src / "__init__.py").is_file()

		if working_is_package:
			root_package_table = PackageTable(self.src.name)
			self.library_table.set_package(root_package_table, self.fqn_map)
			package_map = {self.src: root_package_table}
		else:
			package_map = {self.src: self.library_table}

		for path in self.src.rglob("*"):
			if path.is_dir():
				if "__pycache__" in path.parts:
					continue

				has_init = (path / "__init__.py").is_file()
				if has_init:
					package_table = PackageTable(path.name)
					package_map[path] = package_table
					parent_table = package_map.get(path.parent, self.library_table)
					parent_table.set_package(package_table, self.fqn_map)

			elif path.suffix == ".py":
				package_table = package_map.get(path.parent, self.library_table)
				meta = ModuleMeta.from_source(path, self.library_table)
				package_table.set_module(meta.table, self.fqn_map)
				self.meta_map[meta.table] = meta