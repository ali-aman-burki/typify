import ast
import re

from typing import Any

from typify.preprocessing.module_meta import ModuleMeta

class PreCollector(ast.NodeVisitor):
	UNVISITED = "Any"
	DEFAULT_GUESS = "str"

	_BUILTIN_CALL_GUESS = {
		"int": "int",
		"float": "float",
		"complex": "complex",
		"str": "str",
		"bytes": "bytes",
		"bool": "bool",
		"list": "list",
		"tuple": "tuple",
		"set": "set",
		"dict": "dict",
		"bytearray": "bytearray",
		"memoryview": "memoryview",
		"range": "range",
	}

	_INT_TOKENS    = {"num", "count", "size", "len", "idx", "index", "step", "port", "age", "year", "day", "slot", "slots"}
	_FLOAT_TOKENS  = {"ratio", "score", "prob", "pct", "percent", "lat", "lng", "lon"}
	_BOOL_PREFIXES = ("is_", "has_", "can_", "should_", "use_", "enable_", "disable_", "flag_")
	_STR_TOKENS    = {"path", "file", "dir", "name", "title", "msg", "text", "str", "key", "token", "id", "slug", "url", "uri", "email"}
	_BYTES_TOKENS  = {"bytes", "buf", "blob", "payload"}
	_LIST_TOKENS   = {"items", "values", "lines", "rows", "cols", "list", "array", "queue", "stack", "history", "results"}
	_SET_TOKENS    = {"set", "unique"}
	_DICT_TOKENS   = {"map", "dict", "table", "lookup", "registry", "headers"}

	@staticmethod
	def build_function_signature(
		fdef: ast.FunctionDef | ast.AsyncFunctionDef,
		fqn: str,
		parameters: dict[str, str],
		return_annotation: str
	) -> str:
		args_node = fdef.args
		parts: list[str] = []

		# pos-only
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

		# regular positional
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

		# *args / kw-only separator
		if args_node.vararg:
			name = args_node.vararg.arg
			ann = parameters.get(name, PreCollector.UNVISITED)
			parts.append(f"*{name}: {ann}")
		elif args_node.kwonlyargs:
			parts.append("*")

		# kw-only
		for i, arg in enumerate(args_node.kwonlyargs):
			name = arg.arg
			ann = parameters.get(name, PreCollector.UNVISITED)
			default = args_node.kw_defaults[i]
			part = f"{name}: {ann}"
			if default is not None:
				part += f" = {ast.unparse(default).strip()}"
			parts.append(part)

		# **kwargs
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

	def __init__(self, module_meta: ModuleMeta, typeslots: bool):
		self.module_meta = module_meta
		self.scope_stack: list[tuple[str, str]] = []
		self.typeslots = typeslots
		self.in_function = False

		# imports map visible name -> original base name
		self._imported_names: dict[str, str] = {}

		# local env stack: for each function, a dict expr_text -> guessed type
		# keys are ast.unparse(expr) strings, e.g., "a", "x.y", "x.y.z"
		self._local_env_stack: list[dict[str, str]] = []

	# ---------- utilities ----------

	def _format_fqn(self) -> str:
		return ".".join(f"{kind}:{name}" for kind, name in self.scope_stack)

	def _enclosing_class(self) -> str | None:
		for kind, name in reversed(self.scope_stack):
			if kind == "C":
				return name
		return None

	def _tokenize_name(self, name: str) -> list[str]:
		toks: list[str] = []
		for part in name.split("_"):
			if not part:
				continue
			chunk = []
			last_is_upper = part[0].isupper()
			start = 0
			for i, ch in enumerate(part[1:], 1):
				is_upper = ch.isupper()
				if is_upper and not last_is_upper:
					chunk.append(part[start:i])
					start = i
				last_is_upper = is_upper
			chunk.append(part[start:])
			toks.extend(tok.lower() for tok in chunk if tok)
		return toks

	def _guess_from_name(self, name: str) -> str | None:
		low = name.lower()
		for p in self._BOOL_PREFIXES:
			if low.startswith(p):
				return "bool"
		# Camel/Pascal looks like a class/type
		if re.match(r"^[A-Z][A-Za-z0-9_]*$", name):
			return name

		toks = self._tokenize_name(name)
		score = {"int": 0, "float": 0, "bool": 0, "str": 0, "bytes": 0, "list": 0, "set": 0, "dict": 0}
		for t in toks:
			if t in self._INT_TOKENS:    score["int"] += 2
			if t in self._FLOAT_TOKENS:  score["float"] += 2
			if t in self._STR_TOKENS:    score["str"] += 2
			if t in self._BYTES_TOKENS:  score["bytes"] += 2
			if t in self._LIST_TOKENS:   score["list"] += 2
			if t in self._SET_TOKENS:    score["set"] += 2
			if t in self._DICT_TOKENS:   score["dict"] += 2
		# simple plural bias → list
		if toks and toks[-1].endswith("s") and toks[-1] not in {"is", "has", "cls"}:
			score["list"] += 1

		best_type, best_val = max(score.items(), key=lambda kv: kv[1])
		return best_type if best_val > 0 else None

	def _call_target_name(self, call: ast.Call) -> str | None:
		if isinstance(call.func, ast.Name):
			return call.func.id
		if isinstance(call.func, ast.Attribute):
			return call.func.attr
		return None

	def _guess_from_call(self, call: ast.Call, name_hint: str | None = None) -> str | None:
		target = self._call_target_name(call)
		if not target:
			return None
		if target in self._BUILTIN_CALL_GUESS:
			return self._BUILTIN_CALL_GUESS[target]
		if target in self._imported_names:
			return self._imported_names[target]
		if re.match(r"[A-Z][A-Za-z0-9_]*$", target):
			return target
		if name_hint:
			n = self._guess_from_name(name_hint)
			if n:
				return n
		return None

	def _guess_from_constant(self, value: Any) -> str | None:
		if value is None: return "None"
		if isinstance(value, bool): return "bool"
		if isinstance(value, int): return "int"
		if isinstance(value, float): return "float"
		if isinstance(value, complex): return "complex"
		if isinstance(value, str): return "str"
		if isinstance(value, bytes): return "bytes"
		return None

	def _expr_key(self, expr: ast.AST) -> str | None:
		"""Return a stable textual key for Names/Attributes (for env lookups)."""
		try:
			if isinstance(expr, (ast.Name, ast.Attribute)):
				return ast.unparse(expr)
		except Exception:
			return None
		return None

	def _lookup_env(self, expr: ast.AST, env: dict[str, str]) -> str | None:
		key = self._expr_key(expr)
		if key and key in env:
			return env[key]
		return None

	def _guess_from_expr(self, expr: ast.AST, name_hint: str | None = None, env: dict[str, str] | None = None) -> str:
		# If env is provided and expr is Name/Attribute, try alias propagation first.
		if env is not None and isinstance(expr, (ast.Name, ast.Attribute)):
			aliased = self._lookup_env(expr, env)
			if aliased:
				return aliased

		try:
			if isinstance(expr, ast.Constant):
				gt = self._guess_from_constant(expr.value)
				return gt or self.DEFAULT_GUESS

			if isinstance(expr, (ast.List, ast.ListComp)):
				return "list"
			if isinstance(expr, (ast.Tuple,)):
				return "tuple"
			if isinstance(expr, (ast.Set, ast.SetComp)):
				return "set"
			if isinstance(expr, (ast.Dict, ast.DictComp)):
				return "dict"
			if isinstance(expr, ast.GeneratorExp):
				return "generator"

			if isinstance(expr, ast.Call):
				gt = self._guess_from_call(expr, name_hint=name_hint)
				if gt:
					return gt
				return self.DEFAULT_GUESS

			if isinstance(expr, (ast.BinOp, ast.UnaryOp, ast.Compare)):
				if isinstance(expr, ast.Compare):
					return "bool"
				return "int"

			if isinstance(expr, ast.Name):
				gn = self._guess_from_name(expr.id)
				return gn or self.DEFAULT_GUESS

			if isinstance(expr, ast.Attribute):
				last = expr.attr
				if isinstance(last, str):
					if last in self._imported_names:
						return self._imported_names[last]
					if re.match(r"[A-Z][A-Za-z0-9_]*$", last):
						return last
				return self.DEFAULT_GUESS

		except Exception:
			pass
		return self.DEFAULT_GUESS

	def _guess_from_param_name_against_imports(self, pname: str) -> str | None:
		low = pname.lower()
		best = None
		for alias, orig in self._imported_names.items():
			base = orig.split(".")[-1]
			low_base = base.lower()
			if low == low_base or low in low_base or low_base in low:
				if best is None or len(base) > len(best):
					best = base
		return best

	def _dominant_type(self, candidates: list[str]) -> str:
		if not candidates:
			return self.DEFAULT_GUESS
		counts: dict[str, int] = {}
		for c in candidates:
			counts[c] = counts.get(c, 0) + 1
		# prefer non-"None" on ties
		items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0] == "None"))
		return items[0][0] if items else self.DEFAULT_GUESS

	# ---------- import collection ----------

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

	# ---------- variable slots ----------

	def visit_AnnAssign(self, node: ast.AnnAssign):
		from typify.preprocessing.instance_utils import ReferenceSet

		fqn = self._format_fqn()
		position = (node.target.lineno, node.target.col_offset)
		if self.typeslots or not self.in_function:
			self.module_meta.count_map[position] = 1

		if self.typeslots:
			if node.annotation is not None:
				ann = ast.unparse(node.annotation).strip()
			else:
				# consult env for alias if inside a function
				env = self._local_env_stack[-1] if (self.in_function and self._local_env_stack) else None
				ann = (
					self._guess_from_expr(node.value, name_hint=ast.unparse(node.target), env=env)
					if node.value else self.DEFAULT_GUESS
				)

			self.module_meta.vslots[position] = [
				ast.unparse(node.target),
				ann,
				fqn,
				type(node).__name__,
				ReferenceSet()
			]

			# update local env (names and attributes)
			if self.in_function and self._local_env_stack:
				self._assign_target_env(node.target, ann)

	def visit_Assign(self, node: ast.Assign):
		from typify.preprocessing.instance_utils import ReferenceSet

		fqn = self._format_fqn()
		env = self._local_env_stack[-1] if (self.in_function and self._local_env_stack) else None

		value_is_seq = isinstance(node.value, (ast.Tuple, ast.List))
		elts = node.value.elts if value_is_seq else None

		for target in node.targets:
			packs = PreCollector.collect_targets(target)
			for k, v in packs.items():
				if self.typeslots or not self.in_function:
					self.module_meta.count_map[v] = 1
				if not self.typeslots:
					continue

				guess = None
				if value_is_seq and isinstance(k, (ast.Name, ast.Attribute)):
					try:
						target_names = [t for t in PreCollector.collect_targets(target).keys()]
						if k in target_names:
							idx = target_names.index(k)
							if elts and idx < len(elts):
								guess = self._guess_from_expr(elts[idx], name_hint=ast.unparse(k), env=env)
					except Exception:
						guess = None
				if guess is None:
					# alias propagation: if RHS is Name/Attribute and found in env, reuse that type
					if isinstance(node.value, (ast.Name, ast.Attribute)) and env is not None:
						aliased = self._lookup_env(node.value, env)
						if aliased:
							guess = aliased
					# otherwise general guess (also consult env for nested)
					if guess is None:
						guess = self._guess_from_expr(node.value, name_hint=ast.unparse(k), env=env)

				self.module_meta.vslots[v] = [
					ast.unparse(k),
					guess,
					fqn,
					type(node).__name__,
					ReferenceSet()
				]

				# record into local env (names AND attributes) if in function
				if self.in_function and self._local_env_stack:
					self._assign_target_env(k, guess)

	# ---------- classes & functions ----------

	def visit_ClassDef(self, node: ast.ClassDef):
		self.scope_stack.append(("C", node.name))
		self.generic_visit(node)
		self.scope_stack.pop()

	def _infer_param_type(self, arg: ast.arg, default_expr: ast.AST | None) -> str:
		# annotation wins
		if arg.annotation is not None:
			try:
				return ast.unparse(arg.annotation).strip() or self.DEFAULT_GUESS
			except Exception:
				return self.DEFAULT_GUESS

		name = arg.arg

		# self/cls
		enclosing = self._enclosing_class()
		if enclosing:
			if name == "self":
				return enclosing
			if name == "cls":
				return f"type[{enclosing}]"

		# default expression
		if default_expr is not None:
			return self._guess_from_expr(default_expr, name_hint=name)

		# import-similarity
		match = self._guess_from_param_name_against_imports(name)
		if match:
			return match

		# name heuristics
		byname = self._guess_from_name(name)
		if byname:
			return byname

		return self.DEFAULT_GUESS

	def _gather_return_guesses(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
		"""
		Sequential walk with alias-aware env:
		- tracks local name/attribute -> type guesses as we see assignments
		- resolves return/yield expressions via env when possible
		- explores common blocks (if/for/while/try) with copied envs
		"""
		returns: list[str] = []

		def guess_expr_with_env(expr: ast.AST, env: dict[str, str]) -> str:
			# Names/Attributes: prefer env (alias propagation)
			if isinstance(expr, (ast.Name, ast.Attribute)):
				t = self._lookup_env(expr, env)
				if t:
					return t
			# Otherwise, general guess (which itself may consult env for nested bits)
			return self._guess_from_expr(expr, name_hint=ast.unparse(expr) if hasattr(ast, "unparse") else None, env=env)

		def assign_to_env(target: ast.AST, tname: str, env: dict[str, str]):
			key = self._expr_key(target)
			if key:
				env[key] = tname
			# also assign into elements when destructuring
			if isinstance(target, (ast.Tuple, ast.List)):
				for elt in target.elts:
					assign_to_env(elt, tname, env)

		def handle_assign(targets: list[ast.AST], value: ast.AST, env: dict[str, str]):
			# alias propagation if RHS is Name/Attribute and found in env
			aliased_t: str | None = None
			if isinstance(value, (ast.Name, ast.Attribute)):
				aliased_t = self._lookup_env(value, env)
			if aliased_t is None:
				aliased_t = self._guess_from_expr(value, env=env)

			seq = isinstance(value, (ast.Tuple, ast.List))
			elts = value.elts if seq else None
			if seq:
				# element-wise map across flattened targets
				flat_targets: list[ast.AST] = []
				for t in targets:
					if isinstance(t, (ast.Tuple, ast.List)):
						flat_targets.extend(t.elts)
					else:
						flat_targets.append(t)
				for i, t in enumerate(flat_targets):
					if elts and i < len(elts):
						assign_to_env(t, self._guess_from_expr(elts[i], env=env), env)
					else:
						assign_to_env(t, aliased_t, env)
			else:
				for t in targets:
					assign_to_env(t, aliased_t, env)

		def walk_block(stmts: list[ast.stmt], env: dict[str, str]):
			for s in stmts:
				if isinstance(s, ast.Return):
					if s.value is None:
						returns.append("None")
					else:
						returns.append(guess_expr_with_env(s.value, env))
				elif isinstance(s, ast.Yield):
					returns.append("generator")
				elif isinstance(s, ast.YieldFrom):
					returns.append("generator")
				elif isinstance(s, ast.Assign):
					handle_assign(s.targets, s.value, env)
				elif isinstance(s, ast.AnnAssign):
					tname = (ast.unparse(s.annotation).strip() if s.annotation is not None
					         else self._guess_from_expr(s.value, env=env) if s.value else self.DEFAULT_GUESS)
					assign_to_env(s.target, tname, env)
				elif isinstance(s, ast.AugAssign):
					name_hint = ast.unparse(s.target)
					name_based = self._guess_from_name(name_hint) or None
					tname = name_based if name_based in {"str", "list", "set", "dict"} else "int"
					assign_to_env(s.target, tname, env)
				elif isinstance(s, ast.If):
					walk_block(s.body, env.copy())
					walk_block(s.orelse, env.copy())
				elif isinstance(s, (ast.For, ast.AsyncFor)):
					assign_to_env(s.target, "list", env)
					walk_block(s.body, env.copy())
					walk_block(s.orelse, env.copy())
				elif isinstance(s, ast.While):
					walk_block(s.body, env.copy())
					walk_block(s.orelse, env.copy())
				elif isinstance(s, ast.Try):
					walk_block(s.body, env.copy())
					for h in s.handlers:
						walk_block(h.body, env.copy())
					walk_block(s.orelse, env.copy())
					walk_block(s.finalbody, env.copy())
				elif isinstance(s, (ast.With, ast.AsyncWith)):
					for item in s.items:
						tname = self._guess_from_expr(
							item.context_expr,
							name_hint=ast.unparse(item.optional_vars) if item.optional_vars else None,
							env=env
						)
						if item.optional_vars:
							assign_to_env(item.optional_vars, tname, env)
					walk_block(s.body, env.copy())
				else:
					pass

		env0: dict[str, str] = {}
		walk_block(node.body, env0)

		if returns:
			return self._dominant_type(returns)

		# No explicit returns observed; use name hints
		lowname = node.name.lower()
		if lowname.startswith(("is_", "has_", "can_", "should_")):
			return "bool"
		if lowname.startswith(("iter_", "gen_", "yield_")):
			return "generator"
		if lowname.startswith(("get_", "find_", "read_", "load_", "fetch_")):
			return self.DEFAULT_GUESS
		return "None"

	def _assign_target_env(self, target: ast.AST, tname: str):
		"""Record a guessed type for a target into the current local env (names AND attributes)."""
		if not self._local_env_stack:
			return
		env = self._local_env_stack[-1]
		key = self._expr_key(target)
		if key:
			env[key] = tname
		# propagate to elements on destructuring
		if isinstance(target, (ast.Tuple, ast.List)):
			for elt in target.elts:
				self._assign_target_env(elt, tname)

	def visit_FunctionDef(self, node: ast.FunctionDef):
		from typify.preprocessing.instance_utils import ReferenceSet

		fqn = self._format_fqn()
		position = (node.lineno, node.col_offset)
		param_slots = PreCollector.collect_parameter_slots(node)

		if self.typeslots or not self.in_function:
			self.module_meta.count_map[position] = 2 if self.typeslots else 1

		if self.typeslots:
			args_node = node.args
			# defaults aligned with args
			pos_defaults = [None] * (len(args_node.args) - len(args_node.defaults)) + list(args_node.defaults)
			# crude pos-only alignment (ok for heuristic stage)
			posonly_defaults = [None] * len(args_node.posonlyargs)
			kw_defaults = list(args_node.kw_defaults)

			for i, arg in enumerate(args_node.posonlyargs):
				param_slots[arg.arg] = self._infer_param_type(arg, posonly_defaults[i] if i < len(posonly_defaults) else None)
			for i, arg in enumerate(args_node.args):
				param_slots[arg.arg] = self._infer_param_type(arg, pos_defaults[i] if i < len(pos_defaults) else None)
			if args_node.vararg:
				param_slots[args_node.vararg.arg] = (self._infer_param_type(args_node.vararg, None) or "tuple")
			for i, arg in enumerate(args_node.kwonlyargs):
				param_slots[arg.arg] = self._infer_param_type(arg, kw_defaults[i])
			if args_node.kwarg:
				param_slots[args_node.kwarg.arg] = (self._infer_param_type(args_node.kwarg, None) or "dict")

			# build a fresh local env for this function to support slot writes during visit_*
			self._local_env_stack.append({})
			# compute return annotation using alias-aware mini-walk
			if node.returns is not None:
				try:
					return_ann = ast.unparse(node.returns).strip() or self._gather_return_guesses(node)
				except Exception:
					return_ann = self._gather_return_guesses(node)
			else:
				return_ann = self._gather_return_guesses(node)

			self.module_meta.fslots[position] = [
				node,
				node.name,
				param_slots,
				return_ann,
				fqn,
				{pname: ReferenceSet() for pname in param_slots},
				ReferenceSet()
			]

		self.scope_stack.append(("F", node.name))
		prev_in_function = self.in_function
		self.in_function = True

		# traverse function body (updates local env for var slots)
		self.generic_visit(node)

		self.in_function = prev_in_function
		self.scope_stack.pop()
		if self.typeslots and self._local_env_stack:
			self._local_env_stack.pop()

	def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
		self.visit_FunctionDef(node)
