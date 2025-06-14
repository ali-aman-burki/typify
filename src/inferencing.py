import ast
from src.symbol_table import *
from src.preprocessing.module_meta import ModuleMeta
from src.builtins_ctn import builtins
from src.annotation_types import Type

import copy

class Inferencer(ast.NodeVisitor):
	def __init__(self, module_meta: ModuleMeta, module_object_map: dict[Table, Table]):
		self.library_table = module_meta.library_table
		self.module_meta = module_meta
		self.module_table = module_meta.table
		self.current_table = module_meta.table
		self.latest_definition = self.current_table
		self.module_object_map = module_object_map

	def push(self):
		self.current_table = self.latest_definition.get_enclosing_table()
	
	def pop(self):
		self.latest_definition = self.current_table.parent
		self.current_table = self.current_table.get_enclosing_table()

	def visit_Module(self, node):
		self.generic_visit(node)
		m = builtins.classes["module"]
		module_object = m.create_instance(m)
		Table.transfer_content(self.module_table, module_object)

		if self.module_table.key == "__init__":
			self.module_object_map[self.module_table.parent] = module_object
		else:
			self.module_object_map[self.module_table] = module_object
			if self.module_table.parent not in self.module_object_map:
				self.module_object_map[self.module_table.parent] = m.create_instance(m)

	def process_import(self, name: str, position: tuple[int, int]):
		m = builtins.classes["module"]
		results: list[list[Table]] = []
		for i in range(len(self.module_meta.dependency_map[name])):
			results.append([])
		for i in range(len(self.module_meta.dependency_map[name])):
			chain = self.module_meta.dependency_map[name][i]
			self.module_object_map.setdefault(chain[0], m.create_instance(m))
			cobject = self.module_object_map[chain[0]]
			results[i].append(cobject) 
			for table in chain[1:]:
				self.module_object_map.setdefault(table, m.create_instance(m))
				tobject = self.module_object_map[table]
				if table.key not in cobject.variables:
					mvar = VariableTable(table.key)
					mdef = mvar.add_definition(DefinitionTable(self.module_table, position))
					mdef.type = Type(m)
					mdef.points_to.add(tobject)
					cobject.add_variable(mvar)
				else:
					if tobject not in cobject.variables[table.key].get_latest_definition().points_to:
						mvar = VariableTable(table.key)
						mdef = mvar.add_definition(DefinitionTable(self.module_table, position))
						mdef.type = Type(m)
						mdef.points_to.add(tobject)
						cobject.override_variable(mvar)
				cobject = tobject
				results[i].append(cobject)
			
			return results

	def visit_Import(self, node):
		m = builtins.classes["module"]
		position = (node.lineno, node.col_offset)
		for alias in node.names:
			varname = alias.asname if alias.asname else alias.name.split(".")[0]
			var = self.latest_definition.variables[varname]
			defkey = (self.module_table, position)
			vardef = var.lookup_definition(defkey)
			vardef.type = Type(m)
			results = self.process_import(alias.name, position)
			target_index = -1 if alias.asname else 0

			for chain in results: vardef.points_to.add(chain[target_index])
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