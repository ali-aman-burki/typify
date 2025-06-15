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

	def as_metas(self, modules: set[Table]) -> set[ModuleMeta]:
		return {self.meta_map[table] for table in modules if table in self.meta_map}

	def process_import(self, import_tuple: tuple[ast.Import, Table, bool]):
		node = import_tuple[0]
		enclosing_definition = import_tuple[1]
		in_function = import_tuple[2]
		vars = set()

		for alias in node.names:
			import_module = alias.name
			chains = self.module_meta.resolve_chains(import_module)
			resolved_chains = self.module_meta.filter_chains(chains)
			collected = self.module_meta.collect_modules(resolved_chains)
			self.module_meta.dependency_map[import_module] = chains

			var = VariableTable(alias.asname if alias.asname else import_module.split('.')[0])
			position = (node.lineno, node.col_offset)
			var.add_definition(DefinitionTable(self.module_table, position))

			vars.add(var)

			if not in_function:
				self.module_meta.dependencies.update(self.as_metas(collected))
		
		for var in vars: self.symbols.add(enclosing_definition.add_variable(var))
		
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
						if "__init__" in pac.modules:
							self.module_meta.dependencies.add(self.meta_map[pac.modules["__init__"]])
				elif varkey in chain[-1].modules:
					mod = chain[-1].modules[varkey]
					new_import_module = import_module + "." + varkey
					new_chain = chain + [mod]
					new_chains.append(new_chain)
					if new_import_module not in self.module_meta.dependency_map: 
						self.module_meta.dependency_map[new_import_module] = []
					self.module_meta.dependency_map[new_import_module].append(new_chain)
					if not in_function:
						self.module_meta.dependencies.add(self.meta_map[mod])
			if not in_function:
				resolved_chains = self.module_meta.filter_chains(chains)
				collected = self.module_meta.collect_modules(resolved_chains)
				self.module_meta.dependencies.update(self.as_metas(collected))

		self.module_meta.dependency_map[import_module] = chains

		if not in_function:
			resolved_chains = self.module_meta.filter_chains(chains)
			collected = self.module_meta.collect_modules(resolved_chains)
			self.module_meta.dependencies.update(self.as_metas(collected))