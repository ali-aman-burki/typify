import ast

from copy import deepcopy
from src.symbol_table import Table, VariableTable, DefinitionTable, ModuleTable
from src.typeutils import TypeAnnotation, UnresolvedType

class ParameterSpec:
	def __init__(self, position: tuple[int, int], node: ast.expr | list[ast.expr] | dict[str, ast.expr] | None, kind: str, annotation: ast.AST | None = None):
		self.node = node
		self.position = position
		self.kind = kind
		self.annotation = annotation
		self.type_bundle: tuple[TypeAnnotation, list[Table]] = (UnresolvedType(None), [])

class CallUtils:

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


	@staticmethod
	def map_args_to_params(param_map: dict[str, ParameterSpec], call: ast.Call) -> dict[str, ParameterSpec]:
		if any(isinstance(arg, ast.Starred) for arg in call.args):
			return deepcopy(param_map)
		if any(kw.arg is None for kw in call.keywords):
			return deepcopy(param_map)

		result = deepcopy(param_map)

		pos_keys = [k for k, spec in param_map.items() if spec.kind in ("posonly", "pos_or_kw")]
		vararg_key = next((k for k, spec in param_map.items() if spec.kind == "vararg"), None)
		kwarg_key = next((k for k, spec in param_map.items() if spec.kind == "kwarg"), None)

		for i, arg_node in enumerate(call.args):
			if i < len(pos_keys):
				result[pos_keys[i]].node = arg_node
			elif vararg_key:
				result[vararg_key].node.append(arg_node)
			else:
				return deepcopy(param_map)

		for kw in call.keywords:
			name = kw.arg
			if name in result:
				result[name].node = kw.value
			elif kwarg_key:
				if result[kwarg_key].node is None:
					result[kwarg_key].node = {}
				result[kwarg_key].node[name] = ParameterSpec(
					node=kw.value,
					kind="kwarg"
				)
			else:
				return deepcopy(param_map)

		return result
	
