import ast

from typify.preprocessing.module_meta import ModuleMeta

class PreCollector(ast.NodeVisitor):

	UNVISITED = "Any"
	
	@staticmethod
	def build_function_signature(
		fdef: ast.FunctionDef | ast.AsyncFunctionDef, 
		fqn: str,
		parameters: dict[str, str], 
		return_annotation: str
	) -> str:
		
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

		return f"def {fqn}({', '.join(parts)}) -> {return_annotation}: ..."
	
	@staticmethod
	def collect_parameter_slots(fdef: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, str]:
		args_node = fdef.args
		parameters: dict[str, str] = {}

		for arg in args_node.posonlyargs: parameters[arg.arg] = PreCollector.UNVISITED
		for arg in args_node.args: parameters[arg.arg] = PreCollector.UNVISITED
		for arg in args_node.kwonlyargs: parameters[arg.arg] = PreCollector.UNVISITED

		if args_node.vararg: parameters[args_node.vararg.arg] = PreCollector.UNVISITED
		if args_node.kwarg: parameters[args_node.kwarg.arg] = PreCollector.UNVISITED

		return parameters

	@staticmethod
	def collect_targets(expr: ast.expr) -> dict[ast.expr, tuple[int, int]]:
		targets: dict[ast.expr, tuple[int, int]] = {}

		def visit(node: ast.expr):
			if isinstance(node, (ast.Name, ast.Attribute)):
				targets[node] = (node.lineno, node.col_offset)
			elif isinstance(node, (ast.Tuple, ast.List)):
				for elt in node.elts:
					visit(elt)
			elif isinstance(node, ast.Starred):
				visit(node.value)

		visit(expr)
		return targets

	def __init__(self, module_meta: ModuleMeta):
		self.module_meta = module_meta
		self.scope_stack: list[str] = [module_meta.table.fqn.split(".")[-1]]

	def visit_AnnAssign(self, node):
		fqn = ".".join(self.scope_stack)
		position = (node.target.lineno, node.target.col_offset)
		self.module_meta.vslots[position] = [
			ast.unparse(node.target), 
			PreCollector.UNVISITED, 
			fqn, 
			type(node).__name__
		]

	def visit_Assign(self, node):
		fqn = ".".join(self.scope_stack)
		for target in node.targets:
			packs = PreCollector.collect_targets(target)
			for k, v in packs.items():
				self.module_meta.vslots[v] = [
					ast.unparse(k), 
					PreCollector.UNVISITED, 
					fqn, 
					type(node).__name__
				]

	def visit_AugAssign(self, node):
		fqn = ".".join(self.scope_stack)
		v = (node.target.lineno, node.target.col_offset)
		self.module_meta.vslots[v] = [
			ast.unparse(node.target), 
			PreCollector.UNVISITED, 
			fqn, 
			type(node).__name__
		]

	def visit_ClassDef(self, node):
		self.scope_stack.append(node.name)
		self.generic_visit(node)
		self.scope_stack.pop()

	def visit_FunctionDef(self, node):
		fqn = ".".join(self.scope_stack)
		position = (node.lineno, node.col_offset)
		param_slots = PreCollector.collect_parameter_slots(node)
		self.module_meta.fslots[position] = [node, node.name, param_slots, PreCollector.UNVISITED, fqn]

		self.scope_stack.append(node.name)
		self.generic_visit(node)
		self.scope_stack.pop()
	
	def visit_AsyncFunctionDef(self, node):
		self.visit_FunctionDef(node)  

	def _get_local_fqn(self, name: str) -> str:
		if self.scope_stack:
			return ".".join(self.scope_stack + [name])
		return name