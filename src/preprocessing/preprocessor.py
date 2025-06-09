from pathlib import Path

from src.symbol_table import (
    LibraryTable,
    PackageTable,
    ModuleTable,
)
from src.preprocessing.symbol_slot_collector import SymbolSlotCollector
from src.preprocessing.module_meta import ModuleMeta
from src.preprocessing.graph_utils import GraphUtils
from src.preprocessing.import_processor import ImportCollector

class Preprocessor:

	def __init__(self, working_directory):
		self.working_directory = Path(working_directory).resolve()
		self.library_table = LibraryTable(self.working_directory.name)
		self.meta_map: dict[ModuleTable, ModuleMeta] = {}
		self.dependency_graph: dict[ModuleMeta, list[ModuleMeta]] = {}
	
	def build(self):
		package_map = {self.working_directory: self.library_table}

		for path in self.working_directory.rglob("*"):
			if path.is_dir():
				if "__pycache__" in path.parts:
					continue

				should_process = any((p.suffix == ".py") for p in path.rglob("*"))
				if should_process:
					package_table = PackageTable(path.name)
					package_map[path] = package_table
					parent_table = package_map.get(path.parent, self.library_table)
					parent_table.add_package(package_table)

			elif path.suffix == ".py":
				package_table = package_map.get(path.parent, self.library_table)
				meta = ModuleMeta.from_source(path, self.library_table)
				package_table.add_module(meta.table)
				self.meta_map[meta.table] = meta
				
				SymbolSlotCollector(meta).visit(meta.tree)

		for m in self.meta_map.values():
			ImportCollector(self.meta_map, m).collect()

	def generate_resolving_sequence(self):
		sccs = GraphUtils.tarjan(self.dependency_graph)
		resolving_sequence = GraphUtils.generate_resolving_sequence(sccs)
		return resolving_sequence