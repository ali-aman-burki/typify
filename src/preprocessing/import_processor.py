import ast
from src.symbol_table import VariableTable, Table, ModuleTable, PackageTable, DefinitionTable
from src.builtins_ctn import builtins
from src.preprocessing.module_meta import ModuleMeta
from src.annotation_types import Type
from src.typeutils import TypeUtils

class ImportCollector():
	def __init__(self, meta_map: dict[ModuleTable, ModuleMeta], module_meta: ModuleMeta):
		self.meta_map = meta_map
		self.library_table = module_meta.library_table
		self.module_meta = module_meta
		self.module_table = module_meta.table
		self.path_chain: list[Table] = self.module_table.get_path_chain()

	def collect(self):
		for import_tuple in self.module_meta.imports:
			if isinstance(import_tuple[0], ast.Import): self.process_import(import_tuple)
			else: self.process_import_from(import_tuple)

	def resolve_chains(self, import_chain: list[str]) -> list[list[Table]]:
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
		for chain in chains:
			for i in range(len(chain)):
				table = chain[i]
				if isinstance(table, PackageTable) and "__init__" in table.modules and table.modules["__init__"] != module_table:
					chain[i] = table.modules["__init__"]
		return chains

	def collect_modules(self, resolved_chains: list[list[Table]]) -> set[Table]:
		modules: set[Table] = set()

		for chain in resolved_chains:
			for table in chain:
				if not isinstance(table, PackageTable):
					modules.add(table)

		return modules

	def as_metas(self, modules: set[Table]) -> set[ModuleMeta]:
		return {self.meta_map[table] for table in modules if table in self.meta_map}

	def get_modules(self, level: int, import_chain: list[str], identifiers: set[str]) -> tuple[set[ModuleTable | PackageTable], set[ModuleMeta]]:
		if import_chain:
			if level:
				current = self.path_chain[-level]
				for i in import_chain[:-1]:
					current = current.packages[i]

				search_space = current.packages | current.modules
				current = search_space[import_chain[-1]]

				loaded_tables: set[ModuleTable] = set()

				for table in self.path_chain:
					if "__init__" in table.modules: loaded_tables.add(table.modules["__init__"])
					if isinstance(table, ModuleTable): loaded_tables.add(table)
					if table == current: break

				return ({current}, self.as_metas(loaded_tables))
			else:
				chains = self.resolve_chains(import_chain)
				filtered_chains = self.filter_chains(chains)

				results = []
				for f_chain in filtered_chains:
					endpoint = f_chain[-1]
					if isinstance(endpoint, PackageTable):
						search_space = endpoint.modules.keys()
						if identifiers.issubset(search_space): results.append(f_chain)
					else:
						var_names = endpoint.variables.keys()
						module_names = endpoint.get_enclosing_table().modules.keys() if endpoint.key == "__init__" else set()
						package_names = endpoint.get_enclosing_table().packages.keys() if endpoint.key == "__init__" else set()
						search_space = var_names | package_names | module_names
						if identifiers.issubset(search_space): results.append(f_chain)

				results = results if results else filtered_chains
				collected = self.collect_modules(results)
				return ({f_chain[-1] for f_chain in filtered_chains}, self.as_metas(collected))
		else:
			if level:
				current = self.path_chain[-level]
				loaded_tables: set[ModuleTable] = set()

				for table in self.path_chain:
					if "__init__" in table.modules: loaded_tables.add(table.modules["__init__"])
					if isinstance(table, ModuleTable): loaded_tables.add(table)
					if table == current: break

				return {current, self.as_metas(loaded_tables)}
			else:
				return {}

	def process_import(self, import_tuple: tuple[ast.Import, Table, bool]):
		node = import_tuple[0]
		enclosing_definition = import_tuple[1]
		in_function = import_tuple[2]
		node_str = ast.unparse(node)
		tofill = self.module_meta.dependency_map[node_str] = set()
		m = builtins.classes["module"]

		for alias in node.names:
			import_chain = alias.name.split('.')
			chains = self.resolve_chains(import_chain)
			resolved_chains = self.filter_chains(chains)
			collected = self.collect_modules(resolved_chains)

			var = VariableTable(alias.asname if alias.asname else alias.name.split('.')[0])
			position = (node.lineno, node.col_offset)
			dt = var.add_definition(DefinitionTable(self.module_table, position))
			dt.type = Type(m)

			candidates = set()
			if alias.asname:
				for chain in resolved_chains:
					module_instance = m.create_instance(m)
					if isinstance(chain[-1], ModuleTable): 
						Table.transfer_content(self.meta_map[chain[-1]], module_instance)
					candidates.add(module_instance)
			else:
				for chain in resolved_chains:
					length = len(import_chain)
					adjusted_chain = chain[-length:]
					current_module = m.create_instance(m)
					start_module = current_module
					Table.transfer_content(adjusted_chain[0], current_module)

					for table in adjusted_chain[1:]:
						next_module = m.create_instance(m)
						Table.transfer_content(table, next_module)
						m_var = VariableTable(table.key)
						vd = m_var.add_definition(DefinitionTable(self.module_table, position))
						vd.type = Type(m)
						vd.points_to.add(next_module)
						current_module.add_variable(m_var)
						current_module = next_module
					
					candidates.add(start_module)
			dt.points_to.update(candidates)
			tofill.add(var)

			if not in_function:
				self.module_meta.dependencies.update(self.as_metas(collected))
		
		for var in tofill:
			enclosing_definition.incorporate_variable(var)
		
	def process_import_from(self, import_tuple: tuple[ast.ImportFrom, Table, bool]):
		node = import_tuple[0]
		enclosing_definition = import_tuple[1]
		in_function = import_tuple[2]
		m = builtins.classes["module"]
		node_str = ast.unparse(node)
		tofill = self.module_meta.dependency_map[node_str] = set()
		import_chain = node.module.split('.')
		position = (node.lineno, node.col_offset)
		if node.names[0].name == '*':
			identifiers = {}
		else:
			identifiers = {
				alias.name: VariableTable(alias.asname) if alias.asname else VariableTable(alias.name)
				for alias in node.names
			}
		
		for var in identifiers.values():
			var.add_definition(DefinitionTable(self.module_table, position))
			tofill.add(var)

		data_bundle = self.get_modules(node.level, import_chain, set(identifiers.keys()))
		endpoints = data_bundle[0]
		metas = data_bundle[1]

		if identifiers:
			for endpoint in endpoints:
				if isinstance(endpoint, PackageTable):
					search_space = endpoint.modules
					for id, var in identifiers.items():
						if id in search_space:
							vdt = var.get_latest_definition()
							found_module = search_space[id]
							vdt.collected_types.add(Type(m))
							minstance = m.create_instance(m)
							Table.transfer_content(found_module, minstance)
							vdt.points_to.add(minstance)
				else:
					vars = endpoint.variables
					modules = endpoint.get_enclosing_table().modules if endpoint.key == "__init__" else dict()
					packages = endpoint.get_enclosing_table().packages if endpoint.key == "__init__" else dict()
					search_space = packages | modules | vars

					for id, var in identifiers.items():
						if id in search_space:
							vdt = var.get_latest_definition()
							found_table = search_space[id]
							if isinstance(found_table, PackageTable):
								vdt.collected_types.add(Type(m))
								minstance = m.create_instance(m)
								if "__init__" in found_table.modules:
									Table.transfer_content(found_table.modules["__init__"], minstance)
								vdt.points_to.add(minstance)
							elif isinstance(found_table, ModuleTable):
								vdt.collected_types.add(Type(m))
								minstance = m.create_instance(m)
								Table.transfer_content(found_table, minstance)
								vdt.points_to.add(minstance)
							else:
								ftdt = found_table.get_latest_definition()
								vdt.collected_types.add(ftdt.type)
								vdt.points_to.update(ftdt.points_to)
			for var in identifiers.values():
				vdt = var.get_latest_definition()
				vdt.type = TypeUtils.unify(vdt.collected_types)
		else:
			varkeys = set()
			varmap: dict[str, VariableTable] = {}
			for endpoint in endpoints:
				varkeys.update(endpoint.variables.keys())
			
			for varkey in varkeys:
				var = VariableTable(varkey)
				vdt = var.add_definition(DefinitionTable(self.module_table, position))
				varmap[varkey] = var
				tofill.add(var)

			for endpoint in endpoints:
				for evarkey in endpoint.variables:
					var = varmap[evarkey]
					vdt = var.get_latest_definition()
					evar = endpoint.variables[evarkey]
					evdt = evar.get_latest_definition()
					var.collected_types.add(evdt.type)
					var.points_to.update(evdt.points_to)

			for varkey in varkeys:
				var = varmap[varkey]
				vdt = var.get_latest_definition()
				vdt.type = TypeUtils.unify(vdt.collected_types)
		
		for var in tofill: enclosing_definition.incorporate_variable(var)
		if in_function:
			self.module_meta.dependencies.update(metas)
