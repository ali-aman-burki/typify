import ast

from src.symbol_table import Table, ModuleTable, PackageTable
from src.preprocessing.module_meta import ModuleMeta
from src.preprocessing.library_meta import LibraryMeta

from dataclasses import dataclass

@dataclass
class DependencyBundle:
	libs: list[tuple[str, LibraryMeta]]
	meta_map: dict[ModuleTable, ModuleMeta]
	dependency_graph: dict[ModuleMeta, set[tuple[ModuleMeta, str]]]

class GraphBuilder:
	@staticmethod
	def build_graph(libs: list[tuple[str, LibraryMeta]]) -> DependencyBundle:
		meta_map: dict[ModuleTable, ModuleMeta] = {}
		dependency_graph: dict[ModuleMeta, set[tuple[ModuleMeta, str]]] = {}

		for _, lib in libs: 
			meta_map.update(lib.meta_map)

		for meta in meta_map.values():
			tracker = DependencyTracker(libs, meta_map, dependency_graph, meta)
			
			builtin_node = ast.ImportFrom(module="builtins", names=[ast.alias(name="*", asname=None)], level=0)
			builtin_node.lineno = 0
			builtin_node.col_offset = 0
			meta.tree.body.insert(0, builtin_node)

			tracker.visit(meta.tree)

			if meta.tree.body and meta.tree.body[0] is builtin_node:
				meta.tree.body.pop(0)

		return DependencyBundle(libs, meta_map, dependency_graph)

class DependencyTracker(ast.NodeVisitor):
	def __init__(
		self,
		libs: list[tuple[str, LibraryMeta]],
		meta_map: dict[ModuleTable, ModuleMeta],
		dependency_graph: dict[ModuleMeta, set[tuple[ModuleMeta, str]]],
		module_meta: ModuleMeta
	):
		self.libs = libs
		self.meta_map = meta_map
		self.module_meta = module_meta
		self.module_table = module_meta.table
		self.dependency_graph = dependency_graph
		self.dependency_graph[module_meta] = set()
		self.in_function = 0

		if not module_meta.tree:
			with open(module_meta.src_path, "r", encoding="utf-8") as file:
				source_code = file.read()
			module_meta.tree = ast.parse(source_code)
	
	def as_module_metas(self, modules: list[Table]) -> set[ModuleMeta]:
		return {self.meta_map[table] for table in modules if table in self.meta_map}

	def filter_chain(self, chain: list[PackageTable | ModuleTable]):
		result = []
		for table in chain:
			if isinstance(table, PackageTable): result.append(table.modules["__init__"])
			else: result.append(table)
		return result

	def resolve_fqn_chain(self, module: str | None, level: int = 0) -> list[Table]:
		if level == 0:
			base_fqn = module or ""
		else:
			current_fqn = self.module_table.fqn
			parts = current_fqn.split(".")

			if level > len(parts): return []
			base_parts = parts[:len(parts) - level]
			if module: base_parts.extend(module.split("."))
			base_fqn = ".".join(base_parts)

		for _, lib in self.libs:
			if base_fqn in lib.fqn_map:
				chain = lib.fqn_map[base_fqn]
				metas = self.as_module_metas(self.filter_chain(chain))
				self.dependency_graph[self.module_meta].update(metas)
				self.dependency_graph[self.module_meta].discard(base_fqn)
				return chain

		self.dependency_graph[self.module_meta].add(base_fqn)
		return []


	def visit_Import(self, node):
		if self.in_function: return
		for alias in node.names: self.resolve_fqn_chain(alias.name)
		self.generic_visit(node)

	def visit_ImportFrom(self, node):
		if not self.in_function:
			names = {alias.name for alias in node.names if alias.name != "*"}
			chain = self.resolve_fqn_chain(node.module, node.level)
			if chain:
				endpoint = chain[-1]
				for name in names:
					if name in endpoint.packages:  self.resolve_fqn_chain(endpoint.packages[name].fqn)
					elif name in endpoint.modules:  self.resolve_fqn_chain(endpoint.modules[name].fqn)
				
		self.generic_visit(node)
	
	def visit_FunctionDef(self, node):
		self.in_function += 1
		self.generic_visit(node)
		self.in_function -= 1