from typify.preprocessing.symbol_table import (
	Table, 
	ClassTable, 
	DefinitionTable, 
	VariableTable, 
	FunctionTable
)
from typify.inferencing.function_utils import FunctionUtils

import ast

class ScopeManager:

	@staticmethod
	def class_table(node: ast.ClassDef, enclosing: Table, module_table: Table):
		position = (node.lineno, node.col_offset)
		class_name = node.name
		
		vartable = VariableTable(class_name)
		vartable.add_definition(DefinitionTable(module_table, position))
		enclosing.merge_variable(vartable)

		classtable = ClassTable(class_name)
		classdef = classtable.add_definition(DefinitionTable(module_table, position))
		enclosing.merge_class(classtable)

		return classdef

	def function_table(node: ast.FunctionDef, enclosing: Table, module_table: Table):
		position = (node.lineno, node.col_offset)
		function_name = node.name

		vartable = VariableTable(function_name)
		vartable.add_definition(DefinitionTable(module_table, position))
		enclosing.merge_variable(vartable)
		
		functable = FunctionTable(function_name)
		funcdef = functable.add_definition(DefinitionTable(module_table, position))
		enclosing.merge_function(functable)
		
		funcdef.tree = node
		funcdef.kind = FunctionUtils.get_function_kind(node)
		return funcdef