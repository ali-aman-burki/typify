import ast

from src.context import Context
from copy import deepcopy
from src.symbol_table import Table
from src.typeutils import TypeAnnotation, UnresolvedType

class ParameterSpec:
	def __init__(self, node: ast.expr | list[ast.expr] | dict[str, ast.expr] | None, kind: str, annotation: ast.AST | None = None):
		self.node = node
		self.kind = kind
		self.annotation = annotation
		self.type_bundle: tuple[TypeAnnotation, list[Table]] = (UnresolvedType(None), [])

class CallUtils:
	
	@staticmethod
	def build_parameter_map(funcdef: ast.FunctionDef) -> dict[str, ParameterSpec]:
		args = funcdef.args
		param_map: dict[str, ParameterSpec] = {}

		num_posonly = len(args.posonlyargs)
		num_pos_or_kw = len(args.args)
		total_pos = num_posonly + num_pos_or_kw
		defaults = args.defaults
		default_offset = total_pos - len(defaults)

		for i, arg in enumerate(args.posonlyargs):
			default = defaults[i - default_offset] if i >= default_offset else None
			param_map[arg.arg] = ParameterSpec(
				node=default,
				kind="posonly",
				annotation=arg.annotation
			)

		for i, arg in enumerate(args.args):
			j = i + num_posonly
			default = defaults[j - default_offset] if j >= default_offset else None
			param_map[arg.arg] = ParameterSpec(
				node=default,
				kind="pos_or_kw",
				annotation=arg.annotation
			)

		if args.vararg:
			param_map[f"*{args.vararg.arg}"] = ParameterSpec(
				node=[],
				kind="vararg",
				annotation=args.vararg.annotation
			)

		for kwarg, default in zip(args.kwonlyargs, args.kw_defaults):
			param_map[kwarg.arg] = ParameterSpec(
				node=default,
				kind="kwonly",
				annotation=kwarg.annotation
			)

		if args.kwarg:
			param_map[f"**{args.kwarg.arg}"] = ParameterSpec(
				node=None,
				kind="kwarg",
				annotation=args.kwarg.annotation
			)

		return param_map

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
	
