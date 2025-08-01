import ast

from typify.progbar import ProgressBar
from typify.preprocessing.instance_utils import Instance
from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.core import GlobalContext
from typify.preprocessing.sequencer import Sequencer
from typify.preprocessing.symbol_table import (
    Module, 
    Package, 
)

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
		name: str | None, 
		level: int = 0
	) -> list[Instance]:

		fqn = DependencyUtils.to_absolute_name(defkey[0], name, level)
		for lib in GlobalContext.libs:
			if fqn in lib.fqn_map:
				chain = lib.fqn_map[fqn]

				if all(table.fqn in GlobalContext.sysmodules for table in chain):
					return [GlobalContext.sysmodules[table.fqn] for table in chain]

				modules = []

				if chain[0].fqn not in GlobalContext.sysmodules: break
				
				current_object = GlobalContext.sysmodules[chain[0].fqn]
				modules.append(current_object)

				for table in chain[1:]:
					if table.fqn in GlobalContext.sysmodules:
						current_object = GlobalContext.sysmodules[table.fqn]
						modules.append(current_object)

				return modules

		return []

class GraphBuilder:
	@staticmethod
	def build_graph():
		for lib in GlobalContext.libs:
			GlobalContext.meta_map.update(lib.meta_map)
			GlobalContext.sysmodules.update(lib.sysmodules)

		meta_values = list(GlobalContext.meta_map.values())
		progress = ProgressBar(len(meta_values), prefix="Building dependency graph:")
		progress.display()

		for i, meta in enumerate(meta_values, 1):
			tracker = DependencyTracker(meta)

			meta.load_tree()
			builtin_node = ast.ImportFrom(module="builtins", names=[ast.alias(name="*", asname=None)], level=0)
			builtin_node.lineno = 0
			builtin_node.col_offset = 0
			meta.tree.body.insert(0, builtin_node)

			tracker.visit(meta.tree)

			meta.tree.body.pop(0)

			progress.update(i)

		GlobalContext.cleaned_graph = {
			key: {dep for dep in deps if not isinstance(dep, str)}
			for key, deps in GlobalContext.dependency_graph.items()
		}

		GlobalContext.sequences = Sequencer.generate_sequences(GlobalContext.cleaned_graph)

class DependencyTracker(ast.NodeVisitor):
	def __init__(self, module_meta: ModuleMeta):
		self.module_meta = module_meta
		self.module_table = module_meta.table
		self.in_function = 0

		GlobalContext.dependency_graph[module_meta] = set()
	
	def as_module_metas(self, modules: list[Module]) -> set[ModuleMeta]:
		return {GlobalContext.meta_map[table] for table in modules if table in GlobalContext.meta_map}

	def filter_chain(self, chain: list[Module | Package]):
		result = []
		for table in chain:
			if isinstance(table, Package): result.append(table.modules["__init__"])
			else: result.append(table)
		return result

	def resolve_fqn_chain(self, name: str | None, level: int = 0) -> list[Module | Package]:
		base_fqn = DependencyUtils.to_absolute_name(self.module_table, name, level)

		for lib in GlobalContext.libs:
			if base_fqn in lib.fqn_map:
				chain = lib.fqn_map[base_fqn]
				metas = self.as_module_metas(self.filter_chain(chain))
				GlobalContext.dependency_graph[self.module_meta].update(metas)
				GlobalContext.dependency_graph[self.module_meta].discard(base_fqn)
				return chain

		GlobalContext.dependency_graph[self.module_meta].add(base_fqn)
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