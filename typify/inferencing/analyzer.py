import ast
import copy

from typify.preprocessing.symbol_table import (
	Table,
	ModuleTable, 
	InstanceTable,
)
from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.dependency_utils import DependencyUtils
from typify.inferencing.commons import Builtins
from typify.inferencing.typeutils import TypeUtils

class Analyzer(ast.NodeVisitor):
	def __init__(
			self, 
			module_meta: ModuleMeta, 
			precedence: list[ModuleTable], 
			sysmodules: dict[str, InstanceTable],
			libs: dict[str, LibraryMeta]
		):
		self.module_meta = module_meta
		self.precedence = precedence 
		self.sysmodules = sysmodules
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
		module_object = TypeUtils.instantiate(Builtins.ModuleClass)
		Table.transfer_content(self.module_table, {module_object})
		self.sysmodules[self.module_table.fqn] = module_object
		self.generic_visit(node)

	def visit_Import(self, node):
		position = (node.lineno, node.col_offset)
		defkey = (self.module_table, position)
		
		for alias in node.names:
			varname = alias.asname if alias.asname else alias.name.split(".")[0]
			vartable = self.latest_definition.variables[varname]
			vardef = vartable.lookup_definition(defkey)
			object_chain = DependencyUtils.resolve_module_objects(defkey, self.libs, self.sysmodules, alias.name)
			vardef.points_to.add(object_chain[-1] if alias.asname else object_chain[0])

		self.generic_visit(node)
	
	def visit_ImportFrom(self, node):
		position = (node.lineno, node.col_offset)
		defkey = (self.module_table, position)
		object_chain = DependencyUtils.resolve_module_objects(defkey, self.libs, self.sysmodules, node.module, node.level)
		names = {alias.name for alias in node.names if alias.name != "*"}

		if not names:
			Table.transfer_content(object_chain[-1], {self.module_table, self.sysmodules[self.module_table.fqn]})
		else:
			#for tomorrow
			pass

		self.generic_visit(node)

	def visit_ClassDef(self, node):
		position = (node.lineno, node.col_offset)
		defkey = (self.module_table, position)
		class_name = node.name
		class_table = self.latest_definition.classes[class_name]
		classdef = class_table.lookup_definition(defkey)

		vartable = self.latest_definition.variables[class_name]
		vardef = vartable.lookup_definition(defkey)
		tinstance = TypeUtils.instantiate(Builtins.TypeClass)
		tinstance.origin = classdef
		vardef.points_to.add(tinstance)

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
		func_table = self.latest_definition.functions[func_name]
		funcdef = func_table.lookup_definition(defkey)

		vartable = self.latest_definition.variables[func_name]
		vardef = vartable.lookup_definition(defkey)
		finstance = TypeUtils.instantiate(Builtins.FunctionClass)
		finstance.origin = funcdef
		vardef.points_to.add(finstance)

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