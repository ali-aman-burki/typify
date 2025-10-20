import ast
from typify.preprocessing.module_meta import ModuleMeta


class PreCollector(ast.NodeVisitor):
	DEFAULT_GUESS = ""

	@staticmethod
	def build_function_signature(
		fdef: ast.FunctionDef | ast.AsyncFunctionDef,
		fqn: str,
		parameters: dict[str, str],
		return_annotation: str
	) -> str:
		args_node = fdef.args
		parts: list[str] = []

		pos_params = args_node.posonlyargs + args_node.args
		pos_defaults = [None] * (len(pos_params) - len(args_node.defaults)) + list(args_node.defaults)

		# positional-only args
		for i, arg in enumerate(args_node.posonlyargs):
			name = arg.arg
			ann = parameters.get(name, "")
			default = pos_defaults[i]
			part = f"{name}" if ann == "" else f"{name}: {ann}"
			if default is not None:
				part += f" = {ast.unparse(default).strip()}"
			parts.append(part)

		if args_node.posonlyargs:
			parts.append("/")

		# regular positional args
		for j, arg in enumerate(args_node.args, start=len(args_node.posonlyargs)):
			name = arg.arg
			ann = parameters.get(name, "")
			default = pos_defaults[j]
			part = f"{name}" if ann == "" else f"{name}: {ann}"
			if default is not None:
				part += f" = {ast.unparse(default).strip()}"
			parts.append(part)

		# *args
		if args_node.vararg:
			name = args_node.vararg.arg
			ann = parameters.get(name, "")
			parts.append(f"*{name}" if ann == "" else f"*{name}: {ann}")
		elif args_node.kwonlyargs:
			parts.append("*")

		# keyword-only args
		for i, arg in enumerate(args_node.kwonlyargs):
			name = arg.arg
			ann = parameters.get(name, "")
			default = args_node.kw_defaults[i]
			part = f"{name}" if ann == "" else f"{name}: {ann}"
			if default is not None:
				part += f" = {ast.unparse(default).strip()}"
			parts.append(part)

		# **kwargs
		if args_node.kwarg:
			name = args_node.kwarg.arg
			ann = parameters.get(name, "")
			parts.append(f"**{name}" if ann == "" else f"**{name}: {ann}")

		ret = "" if return_annotation == "" else f" -> {return_annotation}"
		return f"def {fqn}({', '.join(parts)}){ret}: ..."

	@staticmethod
	def collect_parameter_slots(fdef: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, str]:
		args_node = fdef.args
		parameters: dict[str, str] = {}
		for arg in args_node.posonlyargs:
			parameters[arg.arg] = []
		for arg in args_node.args:
			parameters[arg.arg] = []
		for arg in args_node.kwonlyargs:
			parameters[arg.arg] = []
		if args_node.vararg:
			parameters[args_node.vararg.arg] = []
		if args_node.kwarg:
			parameters[args_node.kwarg.arg] = []
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

	def __init__(self, module_meta: ModuleMeta, typeslots: bool, infer: bool):
		self.module_meta = module_meta
		self.scope_stack: list[tuple[str, str]] = []
		self.typeslots = typeslots
		self.infer = infer
		self.in_function = False
		self._imported_names: dict[str, str] = {}
		self._local_env_stack: list[dict[str, str]] = []

	def _format_fqn(self) -> str:
		return ".".join(f"{kind}:{name}" for kind, name in self.scope_stack)

	def _enclosing_class(self) -> str | None:
		for kind, name in reversed(self.scope_stack):
			if kind == "C":
				return name
		return None

	def visit_Import(self, node: ast.Import):
		if not self.typeslots:
			return
		for alias in node.names:
			name = alias.asname or alias.name.split(".")[-1]
			self._imported_names[name] = alias.name

	def visit_ImportFrom(self, node: ast.ImportFrom):
		if not self.typeslots:
			return
		for alias in node.names:
			export = alias.asname or alias.name
			self._imported_names[export] = alias.name

	def visit_AnnAssign(self, node: ast.AnnAssign):
		from typify.preprocessing.instance_utils import ReferenceSet, VSlot
		fqn = self._format_fqn()
		position = (node.target.lineno, node.target.col_offset)

		if self.typeslots or not self.in_function:
			self.module_meta.count_map[position] = 1
		
		vslot = VSlot(
			scope=fqn.replace("F:", "").replace("C:", ""), 
			name=ast.unparse(node.target), 
			u_type=ReferenceSet(),
			h_type=[]
		)

		if self.typeslots:
			self.module_meta.register_vslot(position, vslot)
		
		self.module_meta.register_vslot_snapshot(position, vslot)

	def visit_AugAssign(self, node: ast.AnnAssign):
		from typify.preprocessing.instance_utils import ReferenceSet, VSlot
		fqn = self._format_fqn()
		position = (node.target.lineno, node.target.col_offset)

		if self.typeslots or not self.in_function:
			self.module_meta.count_map[position] = 1
		
		vslot = VSlot(
			scope=fqn.replace("F:", "").replace("C:", ""), 
			name=ast.unparse(node.target), 
			u_type=ReferenceSet(),
			h_type=[]
		)
		if self.typeslots:
			self.module_meta.register_vslot(position, vslot)

		self.module_meta.register_vslot_snapshot(position, vslot)

	def visit_Assign(self, node: ast.Assign):
		from typify.preprocessing.instance_utils import ReferenceSet, VSlot
		fqn = self._format_fqn()

		for bigtarget in node.targets:
			packs = PreCollector.collect_targets(bigtarget)
			for target, position in packs.items():
				if self.typeslots or not self.in_function:
					self.module_meta.count_map[position] = 1
				
				vslot = VSlot(
					scope=fqn.replace("F:", "").replace("C:", ""), 
					name=ast.unparse(target), 
					u_type=ReferenceSet(),
					h_type=[]
				)

				if self.typeslots:
					self.module_meta.register_vslot(position, vslot)

				self.module_meta.register_vslot_snapshot(position, vslot)
				

	def visit_ClassDef(self, node: ast.ClassDef):
		self.scope_stack.append(("C", node.name))
		self.generic_visit(node)
		self.scope_stack.pop()

	def visit_FunctionDef(self, node: ast.FunctionDef):
		from typify.preprocessing.instance_utils import ReferenceSet, FSlot
		fqn = self._format_fqn()
		scope = fqn.replace("F:", "").replace("C:", "")
		position = (node.lineno, node.col_offset)
		h_params = PreCollector.collect_parameter_slots(node)

		if self.typeslots or not self.in_function:
			self.module_meta.count_map[position] = 2 if self.typeslots else 1
		
		fslot = FSlot(
			scope=scope,
			name=node.name,
			u_params={ k: ReferenceSet() for k in h_params },
			h_params=h_params,
			u_ret=ReferenceSet(),
			h_ret=[]
		)
		
		if self.typeslots:
			self.module_meta.register_fslot(position, fslot)

		self.module_meta.register_fslot_snapshot(position, fslot)

		self.scope_stack.append(("F", node.name))
		prev_in_function = self.in_function
		self.in_function = True
		self.generic_visit(node)
		self.in_function = prev_in_function
		self.scope_stack.pop()

	def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
		self.visit_FunctionDef(node)
