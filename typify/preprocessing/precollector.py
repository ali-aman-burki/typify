import ast
import copy

from typify.preprocessing.module_meta import ModuleMeta

class PreCollector(ast.NodeVisitor):

	UNVISITED = "Any"
	
	@staticmethod

	def build_function_signature(fdef: ast.FunctionDef, parameters: dict[str, str], return_annotation: str) -> str:
		args_node = fdef.args
		parts = []

		for i, arg in enumerate(args_node.posonlyargs):
			name = arg.arg
			ann = parameters.get(name, PreCollector.UNVISITED)
			default_idx = i - (len(args_node.posonlyargs) - len(args_node.defaults))
			default = args_node.defaults[default_idx] if default_idx >= 0 else None
			part = f"{name}: {ann}"
			if default is not None:
				part += f" = {ast.unparse(default).strip()}"
			parts.append(part)

		if args_node.posonlyargs:
			parts.append("/")

		total_args = len(args_node.args)
		defaults_offset = total_args - len(args_node.defaults)
		for i, arg in enumerate(args_node.args):
			name = arg.arg
			ann = parameters.get(name, PreCollector.UNVISITED)
			default = args_node.defaults[i - defaults_offset] if i >= defaults_offset else None
			part = f"{name}: {ann}"
			if default is not None:
				part += f" = {ast.unparse(default).strip()}"
			parts.append(part)

		if args_node.vararg:
			name = args_node.vararg.arg
			ann = parameters.get(name, PreCollector.UNVISITED)
			parts.append(f"*{name}: {ann}")
		elif args_node.kwonlyargs:
			parts.append("*")

		for i, arg in enumerate(args_node.kwonlyargs):
			name = arg.arg
			ann = parameters.get(name, PreCollector.UNVISITED)
			default = args_node.kw_defaults[i]
			part = f"{name}: {ann}"
			if default is not None:
				part += f" = {ast.unparse(default).strip()}"
			parts.append(part)

		if args_node.kwarg:
			name = args_node.kwarg.arg
			ann = parameters.get(name, PreCollector.UNVISITED)
			parts.append(f"**{name}: {ann}")

		return f"{fdef.name}({', '.join(parts)}) -> {return_annotation}"

	
	@staticmethod
	def collect_parameter_slots(fdef: ast.FunctionDef) -> dict[str, str]:
		args_node = fdef.args
		parameters: dict[str, str] = {}

		for arg in args_node.posonlyargs: parameters[arg.arg] = PreCollector.UNVISITED
		for arg in args_node.args: parameters[arg.arg] = PreCollector.UNVISITED

		if args_node.vararg: parameters[args_node.vararg.arg] = PreCollector.UNVISITED

		for arg in args_node.kwonlyargs: parameters[arg.arg] = PreCollector.UNVISITED

		if args_node.kwarg: parameters[args_node.kwarg.arg] = PreCollector.UNVISITED

		return parameters

	def __init__(self, module_meta: ModuleMeta):
		self.module_meta = module_meta
		self.module_meta.load_tree()

	def visit_AnnAssign(self, node):
		position = (node.target.lineno, node.target.col_offset)
		self.module_meta.vslots[position] = [node.target, PreCollector.UNVISITED]

	def visit_Assign(self, node):
		for target in node.targets:
			position = (target.lineno, target.col_offset)
			self.module_meta.vslots[position] = [target, PreCollector.UNVISITED]

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

	def visit_FunctionDef(self, node):
		position = (node.lineno, node.col_offset)
		param_slots = PreCollector.collect_parameter_slots(node)
		self.module_meta.fslots[position] = [node, param_slots, PreCollector.UNVISITED]
		self.generic_visit(node)
		
	