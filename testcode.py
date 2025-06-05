import ast
from src.symbol_table import Table, ModuleTable, PackageTable
from src.preprocessing.module_meta import ModuleMeta

class ImportCollector(ast.NodeVisitor):
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
	
	def filter(self, chain_tuples: list[tuple[list[Table], int]]) -> list[tuple[list[Table], int]]:
		module_table = self.module_meta.table
		for table_list, _ in chain_tuples:
			for i in range(len(table_list)):
				table = table_list[i]
				if isinstance(table, PackageTable) and "__init__" in table.modules and table.modules["__init__"] != module_table:
					table_list[i] = table.modules["__init__"]
		return chain_tuples

	def collect(self, chain_tuples: list[tuple[list[Table], int]]) -> set[Table]:
		resolved_chain_tuples = self.filter(chain_tuples)
		modules: set[Table] = set()

		for table_list, _ in resolved_chain_tuples:
			for table in table_list:
				if not isinstance(table, PackageTable):
					modules.add(table)

		return modules

	def as_metas(self, modules: set[Table]) -> set[ModuleMeta]:
		return {self.meta_map[table] for table in modules if table in self.meta_map}

	def visit_Import(self, node: ast.Import):
		for alias in node.names:
			import_chain = alias.name.split('.')
			chain_tuples = self.resolve(import_chain)
			collected = self.collect(chain_tuples)
			self.module_meta.dependency_map[alias.name] = {(chain_tuple[0][-1], chain_tuple[1]) for chain_tuple in chain_tuples}
			self.module_meta.dependencies.update(self.as_metas(collected))

		self.generic_visit()

	def visit_ImportFrom(self, node: ast.ImportFrom):
		if node.module and not node.level:
			import_chain = node.module.split('.')
			identifiers = [alias.name for alias in node.names]
			chain_tuples = self.resolve(import_chain)
			if "*" in identifiers:
				collected = self.collect(chain_tuples)
				self.module_meta.dependency_map[node.module] = {(chain_tuple[0][-1], chain_tuple[1]) for chain_tuple in chain_tuples}
				self.module_meta.dependencies.update(self.as_metas(collected))
				return
			results = []
			for chain in chain_tuples:
				end_point = chain[0][-1]
				if isinstance(end_point, ModuleTable):
					if all(identifier in end_point.variables for identifier in identifiers):
						results.append(chain)
				elif isinstance(end_point, PackageTable):
					module_names = end_point.modules.keys()
					init_vars = end_point.modules["__init__"].variables.keys() if "__init__" in end_point.modules else set()
					search_space = module_names | init_vars
					if all(identifier in search_space for identifier in identifiers):
						results.append(chain)
			
			collected = self.collect(results)
			self.module_meta.dependency_map[node.module] = results
			self.module_meta.dependencies.update(self.as_metas(collected))
		else:
			pass
		self.generic_visit(node)