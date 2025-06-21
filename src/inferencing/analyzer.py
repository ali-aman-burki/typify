import ast
import copy

from src.preprocessing.symbol_table import (
	Table,
	PackageTable, 
	ModuleTable, 
	InstanceTable 
)
from src.preprocessing.module_meta import ModuleMeta
from src.preprocessing.library_meta import LibraryMeta
from src.inferencing.commons import Builtins
from src.inferencing.typeutils import TypeUtils

class Analyzer(ast.NodeVisitor):
	def __init__(
			self, 
			module_meta: ModuleMeta, 
			precedence: list[ModuleTable], 
			module_object_map: dict[PackageTable | ModuleTable, InstanceTable],
			libs: dict[str, LibraryMeta]
		):
		self.module_meta = module_meta
		self.precedence = precedence 
		self.module_object_map = module_object_map
		self.module_table = module_meta.table
		self.current_table = self.module_table
		self.latest_definition = self.current_table
		self.libs = libs

	def push(self):
		self.current_table = self.latest_definition.get_enclosing_table()
	
	def pop(self):
		self.latest_definition = self.current_table.parent
		self.current_table = self.current_table.get_enclosing_table()

	def visit_Module(self, node):
		module_object = TypeUtils.instantiate(Builtins.ModuleClass, [])
		Table.transfer_content(self.module_table, module_object)
		self.module_object_map[self.module_table] = module_object
		if self.module_table.key == "__init__": 
			self.module_object_map[self.module_table.parent] = module_object
		self.generic_visit(node)

	def visit_Import(self, node):
		self.generic_visit(node)
	
	def visit_ImportFrom(self, node):
		self.generic_visit(node)

	def visit_ClassDef(self, node):
		position = (node.lineno, node.col_offset)
		defkey = (self.module_table, position)
		class_name = node.name
		class_table = self.latest_definition.classes[class_name]
		classdef = class_table.lookup_definition(defkey)

		vartable = self.latest_definition.variables[class_name]
		vardef = vartable.lookup_definition(defkey)
		vardef.points_to.add(TypeUtils.instantiate(Builtins.TypeClass, []))

		self.latest_definition = classdef
		self.push()
		self.generic_visit(node)
		self.pop()

	def visit_AsyncFunctionDef(self, node):
		self.visit_FunctionDef(node)

	def visit_FunctionDef(self, node): 
		position = (node.lineno, node.col_offset)
		defkey = (self.module_table, position)
		func_name = node.name

		vartable = self.latest_definition.variables[func_name]
		vardef = vartable.lookup_definition(defkey)
		vardef.points_to.add(TypeUtils.instantiate(Builtins.FunctionClass, []))

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