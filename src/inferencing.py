import ast
from src.symbol_table import *
from src.preprocessing.module_meta import ModuleMeta

import copy

class Inferencer(ast.NodeVisitor):
	def __init__(self, module_meta: ModuleMeta, module_object_map: dict[Table, list[Table]]):
		self.library_table = module_meta.library_table
		self.module_table = module_meta.table
		self.current_table = module_meta.table
		self.latest_definition = self.current_table
		self.module_object_map = module_object_map

	def push(self):
		self.current_table = self.latest_definition.get_enclosing_table()
	
	def pop(self):
		self.latest_definition = self.current_table.parent
		self.current_table = self.current_table.get_enclosing_table()

	def visit_Import(self, node):
		for alias in node.names:
			varname = alias.asname if alias.asname else alias.name.split(".")[0]
			var = self.latest_definition.variables[varname]
			defkey = (self.module_table, node.lineno, node.col_offset)
			vardef = var.lookup_definition(defkey)
			
			
		self.generic_visit(node)

	def visit_ClassDef(self, node):
		class_name = node.name
		class_table = self.latest_definition.classes[class_name]
		defkey = (self.module_table, node.lineno, node.col_offset)
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