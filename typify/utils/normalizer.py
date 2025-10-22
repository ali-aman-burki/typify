import ast, re
from typing import Dict, Any, List, Tuple

def simplify_scope(q: str) -> str:
	if not q:
		return ""
	# remove locals + any lingering C:/F: markers and collapse dots
	q = (q
		 .replace(".<locals>.", ".")
		 .replace("<locals>.", "")
		 .replace(".<locals>", "")
		 .replace("<locals>", "")
		 .replace("C:", "")
		 .replace("F:", ""))
	q = re.sub(r"\.{2,}", ".", q).strip(".")
	return q

# -------- scope & location parsing from anotherformat keys --------
SCOPE_RE = re.compile(
	r"""^
		(?P<prefix>  # e.g., "C:MainPageWidget.F:_setup_datetime.F:state_changed" or ":"
			(?:[CF]:[^:.]+(?:\.[F]:[^:.]+)*)? | :
		)
		:
		(?P<line>\d+):
		(?P<col>\d+)
		$
	""",
	re.X,
)

def parse_key_scope_and_loc(key: str) -> Tuple[str, List[List[int]]]:
	"""
	Convert "C:Class.F:func.F:inner:LINE:COL" → ("Class.func.inner", [[LINE, COL]])
	":"-only prefix (e.g., ":16:0") → ("", [[16,0]])  # module/global scope
	"""
	m = SCOPE_RE.match(key)
	if not m:
		return ("", [])
	prefix = m.group("prefix")
	line, col = int(m.group("line")), int(m.group("col"))

	if prefix == ":":
		return ("", [[line, col]])

	# FIRST: strip all C:/F: tags from the raw scope string
	prefix_clean = prefix.replace("C:", "").replace("F:", "")
	# split + drop empties, then rejoin
	parts = [p for p in prefix_clean.split(".") if p]
	scope = ".".join(parts)
	scope = simplify_scope(scope)
	return (scope, [[line, col]])

# -------- AST helpers --------
def last_name_from_expr(expr_text: str) -> str:
	"""
	Parse an expression like 'self.a.b' or 'obj.attr' or just 'name'
	and return the rightmost identifier ('b', 'attr', or 'name').
	"""
	try:
		node = ast.parse(expr_text, mode="eval").body
	except Exception:
		return expr_text

	while True:
		if isinstance(node, ast.Attribute):
			return node.attr
		if isinstance(node, ast.Name):
			return node.id
		if isinstance(node, ast.Subscript):
			node = node.value
			continue
		if isinstance(node, ast.Call):
			node = node.func
			continue
		try:
			return ast.unparse(node)
		except Exception:
			return expr_text

def parse_signature(sig_src: str) -> Tuple[str, Dict[str, str], str]:
	"""
	Given: "def f(self: C, x: int, *, y: str) -> None: ..."
	Return: (func_name, {param: annotation_str_or_""}, return_annotation_or_"")
	"""
	try:
		mod = ast.parse(sig_src)
	except Exception:
		return ("", {}, "")
	fndef = next((n for n in mod.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
	if not fndef:
		return ("", {}, "")

	def ann_to_str(a):
		if a is None: return ""
		try:
			return ast.unparse(a)
		except Exception:
			return ""

	params: Dict[str, str] = {}

	for a in getattr(fndef.args, "posonlyargs", []):
		params[a.arg] = ann_to_str(a.annotation)
	for a in fndef.args.args:
		params[a.arg] = ann_to_str(a.annotation)

	if fndef.args.vararg:
		params["*"+fndef.args.vararg.arg] = ann_to_str(fndef.args.vararg.annotation)

	for a in fndef.args.kwonlyargs:
		params[a.arg] = ann_to_str(a.annotation)

	if fndef.args.kwarg:
		params["**"+fndef.args.kwarg.arg] = ann_to_str(fndef.args.kwarg.annotation)

	ret = ann_to_str(fndef.returns)
	return (fndef.name, params, ret)

# -------- buckets utilities --------
def to_type_list(s: str) -> List[str]:
	return [s] if s and s.strip() else []

def add_bucket(out: List[Dict[str, Any]], category: str, scope: str, name: str, t: List[str], locs: List[List[int]]):
	out.append({
		"category": category,
		"scope": simplify_scope(scope) or "",
		"name": name,
		"type": t or [],
		"locations": locs or []
	})

# -------- main normalization --------
def normalize_typeslots(key: str, raw: Dict[str, Any]) -> dict[str, List[Dict[str, Any]]]:
	buckets: List[Dict[str, Any]] = []

	# 1) Functions: parse signatures for args & return; use function key for locations & scope pieces
	func_key_to_scope_loc: Dict[str, Tuple[str, List[List[int]]]] = {}
	for fkey, sig in (raw.get("functions") or {}).items():
		scope_from_key, fn_locs = parse_key_scope_and_loc(fkey)
		fname, params, retann = parse_signature(sig)

		if scope_from_key:
			parts = scope_from_key.split(".")
			fq = ".".join(parts + [fname]) if (fname and parts and parts[-1] != fname) else (scope_from_key or fname or "")
		else:
			fq = fname or ""

		# args
		for p_name, p_type in params.items():
			add_bucket(buckets, "argument", fq, p_name, to_type_list(p_type), fn_locs)

		# return (name = function's simple name)
		add_bucket(buckets, "return", fq, fname or "", to_type_list(retann), fn_locs)

		func_key_to_scope_loc[fkey] = (fq, fn_locs)

	# 2) Variables: normalize names, parse scope; merge duplicates per (scope, name)
	merged: Dict[Tuple[str, str], Dict[str, Any]] = {}

	for vkey, vinfo in (raw.get("variables") or {}).items():
		scope_from_key, locs = parse_key_scope_and_loc(vkey)
		fq_scope = scope_from_key

		raw_name = vinfo.get("name", "")
		norm_name = last_name_from_expr(raw_name)

		vtype = vinfo.get("type", "")
		tlist = to_type_list(vtype)

		k = (fq_scope, norm_name)
		if k not in merged:
			merged[k] = {
				"category": "variable",
				"scope": fq_scope,
				"name": norm_name,
				"type": [],
				"locations": []
			}
		for t in tlist:
			if t not in merged[k]["type"]:
				merged[k]["type"].append(t)
		merged[k]["locations"].extend(locs or [])

	# collapse multiple type entries into a single Union[...] string
	for _, payload in merged.items():
		types = payload["type"]
		if len(types) > 1:
			union_str = f"Union[{', '.join(sorted(types))}]"
			payload["type"] = [union_str]
		elif len(types) == 1:
			payload["type"] = [types[0]]
		else:
			payload["type"] = []
		add_bucket(buckets, payload["category"], payload["scope"], payload["name"], payload["type"], payload["locations"])

	return {key: buckets}