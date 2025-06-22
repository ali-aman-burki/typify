import ast
import copy

from typify.preprocessing.symbol_table import (
	Table,
	VariableTable,
	ModuleTable, 
	InstanceTable,
	DefinitionTable
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

		self.pass_index = 0
		self.processed_nodes = set()

	def process(self):
		self.visit(self.module_meta.tree)
		self.pass_index += 1

	def mark_processed(self, node):
		self.processed_nodes.add(node)

	def push(self, entering_def: Table):
		self.latest_definition = entering_def
		self.current_table = entering_def.get_enclosing_table()
	
	def pop(self):
		self.latest_definition = self.current_table.parent
		self.current_table = self.current_table.get_enclosing_table()

	def visit_Module(self, node):
		module_object = TypeUtils.instantiate(Builtins.ModuleClass)
		Table.transfer_names(self.module_table.variables, module_object)
		self.sysmodules[self.module_table.fqn] = module_object
		self.generic_visit(node)

	def visit_Import(self, node):
		if node in self.processed_nodes: return
		
		processed = False
		position = (node.lineno, node.col_offset)
		defkey = (self.module_table, position)
		for alias in node.names:
			varname = alias.asname if alias.asname else alias.name.split(".")[0]
			vartable = self.latest_definition.variables[varname]
			vardef = vartable.lookup_definition(defkey)
			object_chain = DependencyUtils.resolve_module_objects(defkey, self.libs, self.sysmodules, alias.name)
			if not object_chain:
				processed = True
				continue
			vardef.points_to.add(object_chain[-1] if alias.asname else object_chain[0])

		if processed: self.mark_processed(node)
		self.generic_visit(node)
	
	def visit_ImportFrom(self, node):
		if node in self.processed_nodes: return
		
		position = (node.lineno, node.col_offset)
		defkey = (self.module_table, position)
		object_chain = DependencyUtils.resolve_module_objects(defkey, self.libs, self.sysmodules, node.module, node.level)
		
		if not object_chain: return

		if node.names[0].name == "*":
			current_mod_object = self.sysmodules[self.module_table.fqn]
			result = Table.deep_transfer_names(object_chain[-1], self.module_table, defkey, self.precedence)
			Table.transfer_names(result, current_mod_object)
		else:
			for alias in node.names:
				vartable = self.latest_definition.variables[alias.asname if alias.asname else alias.name]
				vardef = vartable.lookup_definition(defkey)
				if alias.name in object_chain[-1].variables:
					modvar = object_chain[-1].variables[alias.name]
					modvardef = modvar.get_latest_definition(defkey, self.precedence)
					vardef.points_to.update(modvardef.points_to)
				else:
					fqn = DependencyUtils.to_absolute_name(self.module_table, node.module, node.level)
					fqn += f".{alias.name}"
					new_object_chain = DependencyUtils.resolve_module_objects(defkey, self.libs, self.sysmodules, fqn)
					vardef.points_to.add(new_object_chain[-1])
					
		self.mark_processed(node)
		self.generic_visit(node)

	def visit_ClassDef(self, node):
		position = (node.lineno, node.col_offset)
		defkey = (self.module_table, position)
		class_name = node.name
		class_table = self.latest_definition.classes[class_name]
		classdef = class_table.lookup_definition(defkey)

		if node in self.processed_nodes:
			self.push(classdef)
			self.generic_visit(node)
			self.pop()
			return

		vartable = self.latest_definition.variables[class_name]
		vardef = vartable.lookup_definition(defkey)
		tinstance = TypeUtils.instantiate(Builtins.TypeClass)
		tinstance.origin = classdef
		vardef.points_to.add(tinstance)

		self.mark_processed(node)
		self.push(classdef)
		self.generic_visit(node)
		self.pop()
		

	def visit_AsyncFunctionDef(self, node):
		self.visit_FunctionDef(node)

	def visit_FunctionDef(self, node): 
		if node in self.processed_nodes: return

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

		self.mark_processed(node)

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