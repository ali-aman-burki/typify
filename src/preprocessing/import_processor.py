import ast
from src.symbol_table import VariableTable, Table, ModuleTable, PackageTable, DefinitionTable
from src.builtins_ctn import builtins
from src.preprocessing.module_meta import ModuleMeta
from src.annotation_types import Type

class ImportCollector(ast.NodeVisitor):
	def __init__(self, meta_map: dict[ModuleTable, ModuleMeta], module_meta: ModuleMeta):
		self.meta_map = meta_map
		self.library_table = module_meta.library_table
		self.module_meta = module_meta
		self.module_table = module_meta.table
		self.path_chain: list[Table] = self.module_table.get_path_chain()
		self.in_function = False

	def resolve(self, import_chain: list[str]) -> list[list[Table]]:
		starting_points: list[list[Table]] = []
		for i in range(len(self.path_chain)):
			table = self.path_chain[i]
			if import_chain[0] in table.modules:
				starting_points.append([table.modules[import_chain[0]]])
			elif import_chain[0] in table.packages: 
				starting_points.append([table.packages[import_chain[0]]])
		
		result = []
		for starting_point in starting_points:
			current = starting_point[0]
			for j in range(1, len(import_chain)):
				if import_chain[j] in current.modules:
					current = current.modules[import_chain[j]]
					starting_point.append(current)
				elif import_chain[j] in current.packages:
					current = current.packages[import_chain[j]]
					starting_point.append(current)
			if len(starting_point) == len(import_chain):
				result.append(starting_point)

		return result
	
	def filter(self, chains: list[list[Table]]) -> list[list[Table]]:
		module_table = self.module_meta.table
		for chain in chains:
			for i in range(len(chain)):
				table = chain[i]
				if isinstance(table, PackageTable) and "__init__" in table.modules and table.modules["__init__"] != module_table:
					chain[i] = table.modules["__init__"]
		return chains

	def collect(self, resolved_chains: list[list[Table]]) -> set[Table]:
		modules: set[Table] = set()

		for chain in resolved_chains:
			for table in chain:
				if not isinstance(table, PackageTable):
					modules.add(table)

		return modules

	def as_metas(self, modules: set[Table]) -> set[ModuleMeta]:
		return {self.meta_map[table] for table in modules if table in self.meta_map}

	def visit_FunctionDef(self, node):
		was_in_function = self.in_function
		self.in_function = True
		self.generic_visit(node)
		self.in_function = was_in_function

	def visit_AsyncFunctionDef(self, node):
		self.visit_FunctionDef(node)

	def visit_Import(self, node: ast.Import):
		node_str = ast.unparse(node)
		tofill = self.module_meta.dependency_map[node_str] = set()

		for alias in node.names:
			import_chain = alias.name.split('.')
			chains = self.resolve(import_chain)
			resolved_chains = self.filter(chains)
			collected = self.collect(resolved_chains)

			var = VariableTable(alias.asname if alias.asname else alias.name.split('.')[0])
			position = (node.lineno, node.col_offset)
			dt = var.add_definition(DefinitionTable(self.module_table, position))
			m = builtins.classes["module"]
			dt.type = Type(m)

			candidates = set()
			if alias.asname:
				for chain in resolved_chains:
					module_instance = m.create_instance(m)
					if isinstance(chain[-1], ModuleTable): 
						Table.module_shallow_copy(self.meta_map[chain[-1]], module_instance)
					candidates.add(module_instance)
			else:
				for chain in resolved_chains:
					length = len(import_chain)
					adjusted_chain = chain[-length:]
					current_module = m.create_instance(m)
					start_module = current_module
					Table.module_shallow_copy(adjusted_chain[0], current_module)

					for table in adjusted_chain[1:]:
						next_module = m.create_instance(m)
						Table.module_shallow_copy(table, next_module)
						m_var = VariableTable(table.key)
						vd = m_var.add_definition(DefinitionTable(self.module_table, position))
						vd.type = Type(m)
						vd.points_to.add(next_module)
						current_module.add_variable(m_var)
						current_module = next_module
					
					candidates.add(start_module)
			dt.points_to.update(candidates)
			tofill.add(var)

			if not self.in_function:
				self.module_meta.dependencies.update(self.as_metas(collected))

	def visit_ImportFrom(self, node: ast.ImportFrom):
		if node.module and not node.level:
			import_chain = node.module.split('.')
			identifiers = [alias.name for alias in node.names]
			chains = self.resolve(import_chain)
			resolved_chains = self.filter(chains)

			if "*" in identifiers:
				collected = self.collect(resolved_chains)
				self.module_meta.dependency_map[node.module] = {
					(self.meta_map[chain[0][-1]], chain[1]) for chain in resolved_chains
				}
				if not self.in_function:
					self.module_meta.dependencies.update(self.as_metas(collected))
				return

			results = []
			for chain in chains:
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

			chains_to_use = results if results else chains
			filtered_results = self.filter(chains_to_use)
			collected = self.collect(filtered_results)
			self.module_meta.dependency_map[node.module] = {
				(self.meta_map[chain[0][-1]], chain[1]) for chain in filtered_results
			}

			if not self.in_function:
				self.module_meta.dependencies.update(self.as_metas(collected))
		else: 
			pass

		self.generic_visit(node)

