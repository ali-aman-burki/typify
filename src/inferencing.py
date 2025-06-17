import ast
from src.symbol_table import *
from src.preprocessing.module_meta import ModuleMeta
from src.typeutils import TypeUtils
from src.preloading.commons import ModuleClass, builtin_lib

import copy

class Inferencer(ast.NodeVisitor):
	def __init__(self, module_meta: ModuleMeta, module_precedence):
		self.module_meta = module_meta
		self.module_precedence = module_precedence
		self.library_table = module_meta.library_table
		self.module_object_map = self.library_table.module_object_map
		self.module_table = module_meta.table
		self.current_table = module_meta.table
		self.latest_definition = self.current_table

	def push(self):
		self.current_table = self.latest_definition.get_enclosing_table()
	
	def pop(self):
		self.latest_definition = self.current_table.parent
		self.current_table = self.current_table.get_enclosing_table()

	def visit_Module(self, node):
		self.generic_visit(node)
		mobject = TypeUtils.create_instance(ModuleClass, [])
		Table.transfer_content(self.module_table, mobject)

		if self.module_table.key == "__init__": self.module_object_map[self.module_table.parent] = mobject
		else: self.module_object_map[self.module_table] = mobject

	def process_import(self, name: str, position: tuple[int, int]):
		results: list[list[Table]] = []
		for i in range(len(self.module_meta.dependency_map[name])):
			results.append([])
		for i in range(len(self.module_meta.dependency_map[name])):
			chain = self.module_meta.dependency_map[name][i]
			cobject = self.module_object_map[chain[0]]
			results[i].append(cobject)
			for table in chain[1:]:
				tobject = self.module_object_map[table]
				if table.key not in cobject.variables:
					mvar = VariableTable(table.key)
					mdef = mvar.add_definition(DefinitionTable(self.module_table, position))
					mdef.points_to.add(tobject)
					cobject.add_variable(mvar)
				else:
					if tobject not in cobject.variables[table.key].get_latest_definition().points_to:
						mvar = VariableTable(table.key)
						mdef = mvar.add_definition(DefinitionTable(self.module_table, position))
						mdef.points_to.add(tobject)
						cobject.override_variable(mvar)
				cobject = tobject
				results[i].append(cobject)
			
		return results

	def visit_Import(self, node):
		position = (node.lineno, node.col_offset)
		for alias in node.names:
			varname = alias.asname if alias.asname else alias.name.split(".")[0]
			var = self.latest_definition.variables[varname]
			defkey = (self.module_table, position)
			vardef = var.lookup_definition(defkey)
			results = self.process_import(alias.name, position)
			target_index = -1 if alias.asname else 0
			for chain in results: vardef.points_to.add(chain[target_index])
		self.generic_visit(node)
	
	def visit_ImportFrom(self, node):
		absolute_name = self.module_meta.to_absolute_name(node.module, node.level)
		position = (node.lineno, node.col_offset)
		defkey = (self.module_table, position)
		results = self.process_import(absolute_name, position)
		
		if node.names[0].name == '*':
			var_dicts = []
			for chain in results: var_dicts.append(chain[-1].variables)
			homogenized = Table.homogenize(var_dicts, defkey, self.module_precedence)
			for v in homogenized.values():
				nv = self.module_table.add_variable(v)
				nv.order_definitions(self.module_precedence)
		else:
			endpoints = [result[-1] for result in results]
			chains = self.module_meta.dependency_map[absolute_name]
			for alias in node.names:
				varkey = alias.asname if alias.asname else alias.name
				var = self.latest_definition.variables[varkey]
				vardef = var.lookup_definition(defkey)
				for i in range(len(endpoints)):
					ep = endpoints[i]
					chain = chains[i]
					if alias.name in ep.variables:
						mvar = ep.variables[alias.name]
						mvardef = mvar.get_latest_definition((vardef.module, vardef.position), self.module_precedence)
						vardef.points_to.update(mvardef.points_to)
					else:
						if alias.name in chain[-1].packages:
							pac = chain[-1].packages[alias.name]
							pobject = self.module_object_map[pac] if pac in self.module_object_map[pac] else TypeUtils.create_instance(ModuleClass, [])
							self.module_object_map[pac] = pobject
							
							pvar = VariableTable(alias.name)
							pdef = pvar.add_definition(DefinitionTable(self.module_table, position))
							pdef.points_to.add(pobject)
							ep.add_variable(pvar)

							vardef.points_to.update(pdef.points_to)

						elif alias.name in chain[-1].modules:
							mod = chain[-1].modules[alias.name]
							mobject = self.module_object_map[mod]
							
							mvar = VariableTable(alias.name)
							mdef = mvar.add_definition(DefinitionTable(self.module_table, position))
							mdef.points_to.add(mobject)
							ep.add_variable(mvar)

							vardef.points_to.update(mdef.points_to)
				
		self.generic_visit(node)

	def visit_ClassDef(self, node):
		position = (node.lineno, node.col_offset)
		class_name = node.name
		class_table = self.latest_definition.classes[class_name]
		defkey = (self.module_table, position)
		self.latest_definition = class_table.lookup_definition(defkey)

		self.push()
		self.generic_visit(node)
		self.pop()

	def visit_AsyncFunctionDef(self, node):
		self.visit_FunctionDef(node)

	def visit_FunctionDef(self, node): pass

	def visit_Return(self, node):
		self.generic_visit(node)

	def visit_Call(self, node):
		self.generic_visit(node)

	def visit_AnnAssign(self, node):
		self.generic_visit(node)

	def visit_Assign(self, node):
		self.generic_visit(node)
	
	def visit_AugAssign(self, node):
		toAssign = ast.Assign(
			targets=[node.target],
			value=ast.BinOp(
				left=copy.deepcopy(node.target),
				op=node.op,
				right=node.value
			)
		)
		ast.copy_location(toAssign, node)
		ast.copy_location(toAssign.value, node)

		toAssign = ast.fix_missing_locations(toAssign)

		self.visit_Assign(toAssign)