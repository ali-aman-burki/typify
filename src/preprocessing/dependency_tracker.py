import ast

from src.symbol_table import Table, ModuleTable, PackageTable
from src.preprocessing.module_meta import ModuleMeta
from src.preprocessing.library_meta import LibraryMeta

from dataclasses import dataclass

@dataclass
class DependencyBundle:
	libs: list[LibraryMeta]
	meta_map: dict[ModuleTable, ModuleMeta]
	dependency_map: dict[str, list[Table]]
	dependency_graph: dict[ModuleMeta, set[ModuleMeta, str]]

class GraphBuilder:
	@staticmethod
	def build_graph(libs: list[LibraryMeta]) -> DependencyBundle:
		meta_map: dict[ModuleTable, ModuleMeta] = {}
		dependency_map: dict[str, list[Table]] = {}
		dependency_graph: dict[ModuleMeta, set[ModuleMeta, str]] = {}
		for lib in libs: meta_map.update(lib.meta_map)

		for meta in meta_map.values():
			tracker = DependencyTracker(libs, meta_map, dependency_map, dependency_graph, meta)
			tracker.visit(meta.tree)
		
		return DependencyBundle(libs, meta_map, dependency_map, dependency_graph)
			
class DependencyTracker(ast.NodeVisitor):
	def __init__(
		self,
		search_libs: list[LibraryMeta],
		meta_map: dict[ModuleTable, ModuleMeta],
		dependency_map: dict[str, list[Table]],
		dependency_graph: dict[ModuleMeta, set[ModuleMeta, str]],
		module_meta: ModuleMeta
	):
		self.meta_map = meta_map
		self.module_meta = module_meta
		self.module_table = module_meta.table
		self.search_libs = search_libs
		self.dependency_map = dependency_map
		self.dependency_graph = dependency_graph
		self.in_function = 0

		if not module_meta.tree:
			with open(module_meta.src_path, "r", encoding="utf-8") as file:
				source_code = file.read()
			module_meta.tree = ast.parse(source_code)
	
	def as_metas(self, modules: set[Table]) -> set[ModuleMeta]:
		return {self.meta_map[table] for table in modules if table in self.meta_map}

	def filter_chain(chain: list[PackageTable | ModuleTable]):
		result = []
		for table in chain:
			if isinstance(table, PackageTable): result.append(table.modules["__init__"])
			else: result.append(table)
		return result

	def visit_FunctionDef(self, node):
		self.in_function += 1
		self.generic_visit(node)
		self.in_function -= 1

	def visit_Import(self, node):
		for alias in node.names:
			fqn_parts = alias.name.split(".")
			chain = []
			for search_lib in self.search_libs:
				lib_table = search_lib.library_table
				if fqn_parts[0] in lib_table.packages:
					current = lib_table.packages[fqn_parts[0]]
					chain.append[current]
					for part in fqn_parts[1:]:
						if part in current.packages: 
							current = current.packages[part]
							chain.append(current)
						elif part in current.modules: 
							current = current.modules[part]
							chain.append(current)
							break
						else: break
					break
				elif fqn_parts[0] in lib_table.modules:
					chain = [lib_table.modules[fqn_parts[0]]]
					break
			
			self.dependency_map[alias.name] = chain
			if not self.in_function:
				if chain: self.dependency_graph[self.module_meta].update(self.filter_chain(chain))
				else: self.dependency_graph[self.module_meta].add(alias.name)
			
	def visit_ImportFrom(self, node):
		self.generic_visit(node)