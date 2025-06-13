import ast
from src.symbol_table import VariableTable, Table, ModuleTable, PackageTable, DefinitionTable
from src.builtins_ctn import builtins
from src.preprocessing.module_meta import ModuleMeta
from src.annotation_types import Type

class ImportCollector():
	def __init__(self, meta_map: dict[ModuleTable, ModuleMeta], module_meta: ModuleMeta):
		self.meta_map = meta_map
		self.library_table = module_meta.library_table
		self.module_meta = module_meta
		self.module_table = module_meta.table
		self.path_chain: list[Table] = self.module_table.get_path_chain()
		self.symbols: set[Table] = set()
	
	def collect(self):
		for import_tuple in self.module_meta.imports:
			if isinstance(import_tuple[0], ast.Import): self.process_import(import_tuple)
			else: self.process_import_from(import_tuple)

	def resolve_chains(self, import_module: str) -> list[list[Table]]:
		import_chain = import_module.split(".")
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

	def filter_chains(self, chains: list[list[Table]]) -> list[list[Table]]:
		module_table = self.module_meta.table
		new_chains = []

		for chain in chains:
			new_chain = []
			for table in chain:
				if isinstance(table, PackageTable) and "__init__" in table.modules and table.modules["__init__"] != module_table:
					new_chain.append(table.modules["__init__"])
				else:
					new_chain.append(table)
			new_chains.append(new_chain)

		return new_chains


	def collect_modules(self, resolved_chains: list[list[Table]]) -> set[Table]:
		modules: set[Table] = set()

		for chain in resolved_chains:
			for table in chain:
				if not isinstance(table, PackageTable):
					modules.add(table)

		return modules

	def as_metas(self, modules: set[Table]) -> set[ModuleMeta]:
		return {self.meta_map[table] for table in modules if table in self.meta_map}

	def process_import(self, import_tuple: tuple[ast.Import, Table, bool]):
		node = import_tuple[0]
		enclosing_definition = import_tuple[1]
		in_function = import_tuple[2]
		vars = set()
		m = builtins.classes["module"]

		for alias in node.names:
			import_module = alias.name
			chains = self.resolve_chains(import_module)
			resolved_chains = self.filter_chains(chains)
			collected = self.collect_modules(resolved_chains)
			self.module_meta.dependency_map[import_module] = chains

			var = VariableTable(alias.asname if alias.asname else import_module.split('.')[0])
			position = (node.lineno, node.col_offset)
			dt = var.add_definition(DefinitionTable(self.module_table, position))
			dt.type = Type(m)

			vars.add(var)

			if not in_function:
				self.module_meta.dependencies.update(self.as_metas(collected))
		
		for var in vars: self.symbols.add(enclosing_definition.add_variable(var))
		
	def process_import_from(self, import_tuple: tuple[ast.ImportFrom, Table, bool]):
		node = import_tuple[0]
		enclosing_definition = import_tuple[1]
		in_function = import_tuple[2]
		import_module = self.module_meta.to_absolute_name(node.module, node.level)
		m = builtins.classes["module"]

		chains = self.resolve_chains(import_module)

		position = (node.lineno, node.col_offset)
		if node.names[0].name == '*':
			identifiers = {}
		else:
			identifiers = {
				alias.name: VariableTable(alias.asname) if alias.asname else VariableTable(alias.name)
				for alias in node.names
			}
		
		for varkey, var in identifiers.items():
			vdt = var.add_definition(DefinitionTable(self.module_table, position))
			self.symbols.add(enclosing_definition.add_variable(var))
			new_chains = []
			for chain in chains:
				if varkey in chain[-1].packages:
					new_import_module = import_module + "." + varkey
					new_chain = chain + [chain[-1].packages[varkey]]
					new_chains.append(new_chain)
					if new_import_module not in self.module_meta.dependency_map: 
						self.module_meta.dependency_map[new_import_module] = []
					self.module_meta.dependency_map[new_import_module].append(new_chain)
					vdt.type = Type(m)
				elif varkey in chain[-1].modules:
					new_import_module = import_module + "." + varkey
					new_chain = chain + [chain[-1].modules[varkey]]
					new_chains.append(new_chain)
					if new_import_module not in self.module_meta.dependency_map: 
						self.module_meta.dependency_map[new_import_module] = []
					self.module_meta.dependency_map[new_import_module].append(new_chain)
					vdt.type = Type(m)
			if not in_function:
				resolved_chains = self.filter_chains(chains)
				collected = self.collect_modules(resolved_chains)
				self.module_meta.dependencies.update(self.as_metas(collected))

		self.module_meta.dependency_map[import_module] = chains

		if not in_function:
			resolved_chains = self.filter_chains(chains)
			collected = self.collect_modules(resolved_chains)
			self.module_meta.dependencies.update(self.as_metas(collected))