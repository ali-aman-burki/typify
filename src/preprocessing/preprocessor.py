from src.symbol_table import LibraryTable, PackageTable, ModuleTable
from src.preprocessing.import_mapper import ImportMapper
from src.preprocessing.symbol_collector import Collector
from src.preprocessing.typeslots_collector import SlotsCollector
from src.preprocessing.module_meta import ModuleMeta
from src.preprocessing.graph_utils import GraphUtils
from pathlib import Path

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
				Collector(meta).visit(meta.tree)
				self.meta_map[meta.table] = meta

	def generate_resolving_sequence(self):
		for m in self.meta_map.values():
			self.dependency_graph[m] = ImportMapper.collect_dependencies(self.meta_map, m)
		for m in self.meta_map.values():
			SlotsCollector(m).visit(m.tree)
		sccs = GraphUtils.tarjan(self.dependency_graph)
		resolving_sequence = GraphUtils.generate_resolving_sequence(sccs)
		return resolving_sequence