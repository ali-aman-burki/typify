from src.symbol_table import Table, ClassTable, DefinitionTable, VariableTable, FunctionTable
from src.function_utils import FunctionUtils
from src.typeutils import TypeUtils
from src.preloading.commons import TypeClass, FunctionClass

import ast

class ScopeManager:

	@staticmethod
	def class_table(node: ast.ClassDef, enclosing: Table, module_table: Table, symbols: set[Table]):
		position = (node.lineno, node.col_offset)
		class_name = node.name
		
		if class_name not in enclosing.variables: 
			symbols.add(enclosing.add_variable(VariableTable(class_name)))
			
		cvt = enclosing.variables[class_name]
		cdvt = cvt.add_definition(DefinitionTable(module_table, position))
		tinstnace = TypeUtils.create_instance(TypeClass, [])
		cdvt.points_to.add(tinstnace)
		parent = enclosing.parent

		if isinstance(parent, ClassTable):
			grandparent = parent.parent
			cvar = grandparent.variables[parent.key]
			for pt in cvar.points_to: pt.add_variable(cvt)

		if class_name not in enclosing.classes:
			result = ClassTable(class_name)
			enclosing.add_class(result)
			symbols.add(result)
		else:
			result = enclosing.classes[class_name]

		cd = result.add_definition(DefinitionTable(module_table, position))
		tinstnace.origin = cd
		return cd

	def function_table(node: ast.FunctionDef, enclosing: Table, module_table: Table, symbols: set[Table]):
		position = (node.lineno, node.col_offset)
		function_name = node.name

		if function_name not in enclosing.variables: 
			symbols.add(enclosing.add_variable(VariableTable(function_name)))
		
		fvt = enclosing.variables[function_name]
		fdvt = fvt.add_definition(DefinitionTable(module_table, position))
		finstance = TypeUtils.create_instance(FunctionClass, [])
		fdvt.points_to.add(finstance)

		if function_name not in enclosing.functions:
			result = FunctionTable(function_name)
			enclosing.add_function(result)
			symbols.add(result)
		else:
			result = enclosing.functions[function_name]
		
		fdt = result.add_definition(DefinitionTable(module_table, position))
		fdt.tree = node
		fdt.kind = FunctionUtils.get_function_kind(node)
		finstance.origin = fdt
		return fdt