import ast
from src.symbol_table import VariableTable, Table, ModuleTable, DefinitionTable
from src.preprocessing.module_meta import ModuleMeta

class DependencyTracker(ast.NodeVisitor):
	def __init__(self, meta_map: dict[ModuleTable, ModuleMeta], module_meta: ModuleMeta):
		self.meta_map = meta_map
		self.library_table = module_meta.library_table
		self.module_meta = module_meta
		self.module_table = module_meta.table
		self.path_chain: list[Table] = self.module_table.get_path_chain()
		self.symbols: set[Table] = set()
		self.in_function = 0
	
	def as_metas(self, modules: set[Table]) -> set[ModuleMeta]:
		return {self.meta_map[table] for table in modules if table in self.meta_map}

	def visit_FunctionDef(self, node):
		self.in_function += 1
		self.generic_visit(node)
		self.in_function -= 1

	def visit_Import(self, node):
		for alias in node.names:
			import_module = alias.name
			chains = self.module_meta.resolve_chains(import_module)
			resolved_chains = self.module_meta.filter_chains(chains)
			collected = self.module_meta.collect_modules(resolved_chains)
			self.module_meta.dependency_map[import_module] = chains

			if not self.in_function:
				self.module_meta.dependencies.update(self.as_metas(collected))
		
	def process_import_from(self, import_tuple: tuple[ast.ImportFrom, Table, bool]):
		node = import_tuple[0]
		enclosing_definition = import_tuple[1]
		in_function = import_tuple[2]
		import_module = self.module_meta.to_absolute_name(node.module, node.level)

		chains = self.module_meta.resolve_chains(import_module)

		position = (node.lineno, node.col_offset)
		if node.names[0].name == '*':
			identifiers = {}
		else:
			identifiers = {
				alias.name: VariableTable(alias.asname) if alias.asname else VariableTable(alias.name)
				for alias in node.names
			}
		
		for varkey, var in identifiers.items():
			var.add_definition(DefinitionTable(self.module_table, position))
			self.symbols.add(enclosing_definition.add_variable(var))
			new_chains = []
			for chain in chains:
				if varkey in chain[-1].packages:
					pac = chain[-1].packages[varkey]
					new_import_module = import_module + "." + varkey
					new_chain = chain + [pac]
					new_chains.append(new_chain)
					if new_import_module not in self.module_meta.dependency_map: 
						self.module_meta.dependency_map[new_import_module] = []
					self.module_meta.dependency_map[new_import_module].append(new_chain)
					if not in_function:
						if "__init__" in pac.modules and pac.modules["__init__"] in self.meta_map:
							self.module_meta.dependencies.add(self.meta_map[pac.modules["__init__"]])
				elif varkey in chain[-1].modules:
					mod = chain[-1].modules[varkey]
					new_import_module = import_module + "." + varkey
					new_chain = chain + [mod]
					new_chains.append(new_chain)
					if new_import_module not in self.module_meta.dependency_map: 
						self.module_meta.dependency_map[new_import_module] = []
					self.module_meta.dependency_map[new_import_module].append(new_chain)
					if not in_function and mod in self.meta_map:
						self.module_meta.dependencies.add(self.meta_map[mod])

		self.module_meta.dependency_map[import_module] = chains

		if not in_function:
			resolved_chains = self.module_meta.filter_chains(chains)
			collected = self.module_meta.collect_modules(resolved_chains)
			self.module_meta.dependencies.update(self.as_metas(collected))