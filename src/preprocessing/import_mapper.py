import ast
from src.symbol_table import Table, ModuleTable, PackageTable
from src.preprocessing.module_meta import ModuleMeta

class ImportMapper:
	@staticmethod
	def collect_dependencies(meta_map: dict[ModuleTable, ModuleMeta], module_meta: ModuleMeta) -> set[ModuleTable]:
		traverser = ImporTraverser(meta_map, module_meta)
		traverser.visit(module_meta.ast_rep)
		return module_meta.dependencies

class ImporTraverser(ast.NodeVisitor):
	def __init__(self, meta_map: dict[ModuleTable, ModuleMeta], module_meta: ModuleMeta):
		self.meta_map = meta_map
		self.library_table = module_meta.library_table
		self.module_meta = module_meta
		self.module_table = module_meta.table
		self.path_chain: list[Table] = self.module_table.get_path_chain()

	def resolve(self, import_chain: list[str]) -> list[tuple[list[Table], int]]:
		starting_points: list[tuple[list[Table], int]] = []
		for i in range(len(self.path_chain)):
			table = self.path_chain[i]
			if import_chain[0] in table.modules:
				starting_points.append(([table.modules[import_chain[0]]], i))
			elif import_chain[0] in table.packages: 
				starting_points.append(([table.packages[import_chain[0]]], i))
		
		result = []
		for starting_point in starting_points:
			current_list = starting_point[0]
			current = current_list[0]
			for j in range(1, len(import_chain)):
				if import_chain[j] in current.modules:
					current = current.modules[import_chain[j]]
					current_list.append(current)
				elif import_chain[j] in current.packages:
					current = current.packages[import_chain[j]]
					current_list.append(current)
			if len(current_list) == len(import_chain):
				result.append(starting_point)

		return result
	
	def filter(self, chains: list[tuple[list[Table], int]]) -> list[tuple[list[Table], int]]:
		module_table = self.module_meta.table
		for table_list, _ in chains:
			for i in range(len(table_list)):
				table = table_list[i]
				if isinstance(table, PackageTable) and "__init__" in table.modules and table.modules["__init__"] != module_table:
					table_list[i] = table.modules["__init__"]
		return chains

	def collect(self, import_chain: list[str]) -> set[Table]:
		chains = self.resolve(import_chain)
		resolved_chains = self.filter(chains)
		modules: set[Table] = set()

		for table_list, _ in resolved_chains:
			for table in table_list:
				if not isinstance(table, PackageTable):
					modules.add(table)

		return modules

	def as_metas(self, modules: set[Table]) -> set[ModuleMeta]:
		return {self.meta_map[table] for table in modules if table in self.meta_map}

	def visit_Import(self, node):
		for alias in node.names:
			import_chain = alias.name.split('.')
			per_import_denepdencies = self.resolve(import_chain)
			self.module_meta.dependency_map[alias.name] = per_import_denepdencies
			collected = self.collect(import_chain)
			self.module_meta.dependencies.update(self.as_metas(collected))

		self.generic_visit(node)

	def visit_ImportFrom(self, node):
		self.generic_visit(node)