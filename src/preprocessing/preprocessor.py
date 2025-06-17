from pathlib import Path

from src.symbol_table import (
    Table,
	LibraryTable,
    PackageTable,
    ModuleTable,
)
from src.preprocessing.symbol_slot_collector import SymbolSlotCollector
from src.preprocessing.module_meta import ModuleMeta
from src.preprocessing.graph_utils import GraphUtils
from src.preprocessing.import_processor import ImportCollector
from src.typeutils import TypeUtils
from src.preloading.commons import builtin_lib

class Preprocessor:

	def __init__(self, working_directory):
		self.working_directory = Path(working_directory).resolve()
		self.library_table = LibraryTable(self.working_directory.name)
		self.module_object_map = self.library_table.module_object_map
		self.meta_map: dict[ModuleTable, ModuleMeta] = {}
		self.dependency_graph: dict[ModuleMeta, set[ModuleMeta]] = {}
		self.symbols: set[Table] = set()
	
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

					if not (path / "__init__.py").exists():
						self.module_object_map[package_table] = TypeUtils.create_instance(
							builtin_lib.modules["builtins"].classes["module"], []
							)

			elif path.suffix == ".py":
				package_table = package_map.get(path.parent, self.library_table)
				meta = ModuleMeta.from_source(path, self.library_table)
				package_table.add_module(meta.table)
				self.meta_map[meta.table] = meta
				
				ssc = SymbolSlotCollector(meta)
				ssc.visit(meta.tree)
				self.symbols.update(ssc.symbols)
		
		for meta in self.meta_map.values():
			ic = ImportCollector(self.meta_map, meta)
			ic.collect()
			self.symbols.update(ic.symbols)
			self.dependency_graph[meta] = meta.dependencies

	def generate_resolving_sequence(self):
		# for k, v in self.dependency_graph.items():
		# 	joined = ",".join(repr(repr(m)) for m in v)
		# 	print(f"{k} -> [{joined}]")

		sccs = GraphUtils.tarjan(self.dependency_graph)
		resolving_sequence = GraphUtils.generate_resolving_sequence(sccs)
		# joined = "\n".join([repr(m) for m in resolving_sequence])
		# print("\nsequence:")
		# print(joined)
		return resolving_sequence