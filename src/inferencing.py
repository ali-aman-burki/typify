import ast
from src.symbol_table import *
from src.preprocessing.module_meta import ModuleMeta

import copy

class Inferencer(ast.NodeVisitor):
	def __init__(self, module_meta: ModuleMeta):
		self.library_table = module_meta.library_table
		self.module_table = module_meta.table
		self.current_table = module_meta.table

	def visit_ClassDef(self, node):
		self.generic_visit(node)

	def visit_AsyncFunctionDef(self, node):
		self.visit_FunctionDef(node)

	def visit_FunctionDef(self, node):
		self.generic_visit(node)

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