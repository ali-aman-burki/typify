from src.symbol_table import Table, ClassTable, DefinitionTable, VariableTable, FunctionTable
from src.builtins_ctn import builtins
from src.annotation_types import Type

import ast

class ScopeManager:

	@staticmethod
	def class_table(node: ast.ClassDef, enclosing: Table):
		position = (node.lineno, node.col_offset)
		class_name = node.name
		
		if class_name not in enclosing.variables: 
			enclosing.add_variable(VariableTable(class_name))
		cvt = enclosing.variables[class_name]
		cdvt = cvt.add_definition(DefinitionTable(cvt.get_enclosing_module(), position))
		t = builtins.classes["type"]
		cdvt.type = Type(t)
		tinstnace = t.create_instance(t)
		cdvt.points_to.add(tinstnace)

		if class_name not in enclosing.classes:
			result = ClassTable(class_name)
			enclosing.add_class(result)
		else:
			result = enclosing.classes[class_name]

		cd = result.add_definition(DefinitionTable(result.get_enclosing_module(), position))
		tinstnace.returns.add(cd)
		return cd

	def function_table(node: ast.FunctionDef, enclosing: Table):
		position = (node.lineno, node.col_offset)
		function_name = node.name

		if function_name not in enclosing.variables: 
			enclosing.add_variable(VariableTable(function_name))
		
		fvt = enclosing.variables[function_name]
		fdvt = fvt.add_definition(DefinitionTable(fvt.get_enclosing_module(), position))
		f = builtins.classes["function"]
		fdvt.type = Type(f)
		finstance = f.create_instance(f)
		fdvt.points_to.add(finstance)

		if function_name not in enclosing.functions:
			function_table = FunctionTable(function_name)
			enclosing.add_function(function_table)
		else:
			function_table = enclosing.functions[function_name]
		
		fdt = function_table.add_definition(DefinitionTable(function_table.get_enclosing_module(), position))
		fdt.tree = node
		finstance.returns.add(fdt)
		return fdt