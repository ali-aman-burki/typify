import ast

from typify.preprocessing.instance_utils import Instance
from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.sequencer import Sequencer
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.commons import Builtins
from typify.preprocessing.symbol_table import (
    Symbol,
    Module, 
    Package, 
	NameDefinition
)

from dataclasses import dataclass

@dataclass
class DependencyBundle:
	libs: list[LibraryMeta]
	meta_map: dict[Module, ModuleMeta]
	sysmodules: dict[str, Instance]
	dependency_graph: dict[ModuleMeta, set[ModuleMeta | str]]
	cleaned_graph: dict[ModuleMeta, set[ModuleMeta]]
	sequences: list[list[ModuleMeta]]

class DependencyUtils:

	@staticmethod
	def to_absolute_name(module_table: Module, name: str | None, level: int = 0) -> str:
		level = max(0, level)
		
		if level == 0:
			base_fqn = name or ""
		else:
			current_fqn = module_table.fqn
			parts = current_fqn.split(".")
			
			level = min(level, len(parts))
			base_parts = parts[:len(parts) - level]
			if name:
				base_parts.extend(name.split("."))
			base_fqn = ".".join(base_parts)
		
		return base_fqn

	@staticmethod
	def resolve_module_objects(
		defkey: tuple[Module, tuple[int, int]], 
		libs: list[LibraryMeta], 
		sysmodules: dict[str, Instance],
		name: str | None, 
		level: int = 0
	) -> list[Instance]:
		fqn = DependencyUtils.to_absolute_name(defkey[0], name, level)
		for lib in libs:
			if fqn in lib.fqn_map:
				chain = lib.fqn_map[fqn]

				if all(table.fqn in sysmodules for table in chain):
					return [sysmodules[table.fqn] for table in chain]

				modules = []

				if chain[0].fqn not in sysmodules: break
				
				current_object = sysmodules[chain[0].fqn]
				modules.append(current_object)

				for table in chain[1:]:
					if table.fqn in sysmodules:
						current_object = sysmodules[table.fqn]
						modules.append(current_object)
						continue
					
					module_object = TypeUtils.instantiate_with_args(Builtins.get_type("module"))
					Symbol.transfer_names(table.names, module_object)

					attrdef = NameDefinition(defkey)
					attrdef.refset.add(module_object)
					current_object.get_name(table.id).set_definition(attrdef)

					sysmodules[table.fqn] = module_object
					current_object = module_object
					modules.append(current_object)

				return modules

		return []

class GraphBuilder:
	@staticmethod
	def build_graph(libs: list[LibraryMeta]) -> DependencyBundle:
		meta_map: dict[Module, ModuleMeta] = {}
		sysmodules: dict[Package | Module, Instance] = {}
		dependency_graph: dict[ModuleMeta, set[ModuleMeta | str]] = {}

		for lib in libs:
			meta_map.update(lib.meta_map)
			sysmodules.update(lib.sysmodules)

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

		sequences = Sequencer.generate_sequences(cleaned_graph)

		return DependencyBundle(
			libs,
			meta_map,
			sysmodules,
			dependency_graph,
			cleaned_graph,
			sequences
		)

class DependencyTracker(ast.NodeVisitor):
	def __init__(
		self,
		libs: list[LibraryMeta],
		meta_map: dict[Module, ModuleMeta],
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
	
	def as_module_metas(self, modules: list[Module]) -> set[ModuleMeta]:
		return {self.meta_map[table] for table in modules if table in self.meta_map}

	def filter_chain(self, chain: list[Module | Package]):
		result = []
		for table in chain:
			if isinstance(table, Package): result.append(table.modules["__init__"])
			else: result.append(table)
		return result

	def resolve_fqn_chain(self, name: str | None, level: int = 0) -> list[Module | Package]:
		base_fqn = DependencyUtils.to_absolute_name(self.module_table, name, level)

		for lib in self.libs:
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
					if isinstance(endpoint, Package):
						if name in endpoint.packages: 
							self.resolve_fqn_chain(endpoint.packages[name].fqn)
						elif name in endpoint.modules: 
							self.resolve_fqn_chain(endpoint.modules[name].fqn)
				
		self.generic_visit(node)
	
	def visit_FunctionDef(self, node):
		self.in_function += 1
		self.generic_visit(node)
		self.in_function -= 1