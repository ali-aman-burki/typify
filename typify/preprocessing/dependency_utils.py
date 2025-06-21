import ast

from typify.preprocessing.symbol_table import Table, ModuleTable, PackageTable, InstanceTable
from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.sequencer import Sequencer

from dataclasses import dataclass

@dataclass
class DependencyBundle:
	libs: dict[str, LibraryMeta]
	meta_map: dict[ModuleTable, ModuleMeta]
	module_object_map: dict[PackageTable | ModuleTable, InstanceTable]
	dependency_graph: dict[ModuleMeta, set[ModuleMeta | str]]
	cleaned_graph: dict[ModuleMeta, set[ModuleMeta]]
	resolving_sequence: list[ModuleMeta]

class GraphBuilder:
	@staticmethod
	def build_graph(libs: dict[str, LibraryMeta]) -> DependencyBundle:
		meta_map: dict[ModuleTable, ModuleMeta] = {}
		module_object_map: dict[PackageTable | ModuleTable, InstanceTable] = {}
		dependency_graph: dict[ModuleMeta, set[ModuleMeta | str]] = {}

		for lib in libs.values():
			meta_map.update(lib.meta_map)
			module_object_map.update(lib.module_object_map)

		for meta in meta_map.values():
			tracker = DependencyTracker(libs, meta_map, dependency_graph, meta)

			meta.load_tree()
			builtin_node = ast.ImportFrom(module="builtins", names=[ast.alias(name="*", asname=None)], level=0)
			builtin_node.lineno = 0
			builtin_node.col_offset = 0
			meta.tree.body.insert(0, builtin_node)

			tracker.visit(meta.tree)

			meta.tree.body.pop(0)

		cleaned_graph: dict[ModuleMeta, set[ModuleMeta]] = {
			key: {dep for dep in deps if not isinstance(dep, str)}
			for key, deps in dependency_graph.items()
		}

		resolving_sequence = Sequencer.generate_resolving_sequence(cleaned_graph)

		return DependencyBundle(
			libs,
			meta_map,
			module_object_map,
			dependency_graph,
			cleaned_graph,
			resolving_sequence
		)

class DependencyTracker(ast.NodeVisitor):
	def __init__(
		self,
		libs: dict[str, LibraryMeta],
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

		for lib in self.libs.values():
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