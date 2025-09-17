import ast
from collections import defaultdict
from typing import Any, Dict, List, Tuple

def normalize_inferred_types(inferred: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    if "variables" not in inferred and "functions" not in inferred:
        if not inferred:
            return {"global@global": []}
        inferred = next(iter(inferred.values()))

    var_entries = inferred.get("variables", {}) or {}
    func_entries = inferred.get("functions", {}) or {}

    collected: dict[str, dict[Tuple[str, str], set[str]]] = defaultdict(lambda: defaultdict(set))

    collected["global@global"]

    def _unparse(ann: ast.AST | None) -> str:
        if ann is None:
            return "Any"
        try:
            return ast.unparse(ann)
        except Exception:
            return "Any"

    def _func_key(func_name: str, class_stack: List[str]) -> str:
        return f"{func_name}@{','.join(class_stack) if class_stack else 'global'}"

    def _parse_context(encoded_key: str) -> tuple[list[str], str | None]:
        class_stack: list[str] = []
        func_name: str | None = None
        for seg in encoded_key.split("."):
            if seg.startswith("C:"):
                class_stack.append(seg[2:].split(":")[0])
            elif seg.startswith("F:"):
                func_name = seg[2:].split(":")[0]
        return class_stack, func_name

    def _var_display_name(raw_name: str) -> str:
        if "." not in raw_name:
            return raw_name
        parts = raw_name.split(".")
        root = parts[0]
        if root == "self":
            return parts[-1]
        return f"{root}_"

    def _ensure_class_buckets(class_stack: List[str]) -> None:
        for i in range(1, len(class_stack) + 1):
            collected[_func_key("class", class_stack[:i])]

    for encoded_key, sig in func_entries.items():
        class_stack, _ = _parse_context(encoded_key)

        _ensure_class_buckets(class_stack)

        fn_mod = ast.parse(sig)
        fn = fn_mod.body[0]
        assert isinstance(fn, ast.FunctionDef)

        key = _func_key(fn.name, class_stack)

        def add_arg(a: ast.arg | None) -> None:
            if a is None:
                return
            collected[key][("arg", a.arg)].add(_unparse(a.annotation))

        for a in getattr(fn.args, "posonlyargs", []):
            add_arg(a)
        for a in fn.args.args:
            add_arg(a)
        if fn.args.vararg:
            add_arg(fn.args.vararg)
        for a in fn.args.kwonlyargs:
            add_arg(a)
        if fn.args.kwarg:
            add_arg(fn.args.kwarg)

        collected[key][("return", fn.name)].add(_unparse(fn.returns))

    for encoded_key, info in var_entries.items():
        class_stack, maybe_func = _parse_context(encoded_key)

        _ensure_class_buckets(class_stack)

        raw_name = info.get("name", "")
        typ = info.get("type", "Any")

        if maybe_func:
            key = _func_key(maybe_func, class_stack)
            category = "local"
            name = _var_display_name(raw_name)
        else:
            key = _func_key("class", class_stack)
            category = "classvar"
            name = raw_name.split(".")[-1] if raw_name else raw_name

        collected[key][(category, name)].add(str(typ))

    result: Dict[str, List[Dict[str, Any]]] = {}
    order = {"arg": 0, "local": 1, "return": 2}
    for key, slots in collected.items():
        bucket: list[dict[str, Any]] = []
        for (category, name), typeset in slots.items():
            bucket.append({"category": category, "name": name, "type": sorted(typeset)})
        bucket.sort(key=lambda d: (order.get(d["category"], 9), d["name"]))
        result[key] = bucket

    return result