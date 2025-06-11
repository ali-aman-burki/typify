import ast

from src.symbol_table import VariableTable, DefinitionTable, ModuleTable, InstanceTable

class FunctionUtils:

	@staticmethod
	def call_function(caller: InstanceTable, function_name, arguments: dict[str, VariableTable], call_site: tuple[ModuleTable, tuple[int, int]]):
		fdt = caller.origin.functions[function_name].get_latest_definition()
		
		pass

	@staticmethod
	def get_function_kind(fdef: ast.FunctionDef) -> str:
		for decorator in fdef.decorator_list:
			if isinstance(decorator, ast.Name):
				if decorator.id == "classmethod": return "classmethod"
				elif decorator.id == "staticmethod": return "staticmethod"
			elif isinstance(decorator, ast.Attribute):
				if decorator.attr == "classmethod": return "classmethod"
				elif decorator.attr == "staticmethod": return "staticmethod"
		return ""

	@staticmethod
	def collect_parameters(fdef: ast.FunctionDef, module_table: ModuleTable) -> dict[str, VariableTable]:
		args_node = fdef.args
		parameters: dict[str, VariableTable] = {}

		for arg in args_node.posonlyargs:
			var = parameters[arg.arg] = VariableTable(arg.arg)
			position = (arg.lineno, arg.col_offset)
			var.add_definition(DefinitionTable(module_table, position))

		for arg in args_node.args:
			var = parameters[arg.arg] = VariableTable(arg.arg)
			position = (arg.lineno, arg.col_offset)
			var.add_definition(DefinitionTable(module_table, position))

		if args_node.vararg:
			var = parameters[args_node.vararg.arg] = VariableTable(args_node.vararg.arg)
			position = (args_node.vararg.lineno, args_node.vararg.col_offset)
			var.add_definition(DefinitionTable(module_table, position))

		for arg in args_node.kwonlyargs:
			var = parameters[arg.arg] = VariableTable(arg.arg)
			position = (arg.lineno, arg.col_offset)
			var.add_definition(DefinitionTable(module_table, position))

		if args_node.kwarg:
			var = parameters[args_node.kwarg.arg] = VariableTable(args_node.kwarg.arg)
			position = (args_node.kwarg.lineno, args_node.kwarg.col_offset)
			var.add_definition(DefinitionTable(module_table, position))

		return parameters
	
