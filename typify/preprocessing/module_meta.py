from pathlib import Path
import ast, json

from typify.preprocessing.symbol_table import Module

class ModuleMeta:

	def __init__(self, src: Path, trust_annotations: bool):
		from typify.inferencing.expression import TypeExpr
		from typify.preprocessing.instance_utils import ReferenceSet

		self.src = src
		self.tree: ast.AST = None
		self.table = Module(src.stem)
		self.trust_annotations = trust_annotations

		self.vslots: dict[tuple[int, int], list[str | ReferenceSet]] = {}
		self.fslots: dict[tuple[int, int], list[ast.FunctionDef | ast.AsyncFunctionDef | str | dict[str, ReferenceSet] | ReferenceSet]] = {}

	def load_tree(self):
		if not self.tree:
			with open(self.src, "r", encoding="utf-8") as file:
				src_code = file.read()
			self.tree = ast.parse(src_code)

	def __repr__(self):
		return self.table.fqn
	
	def mirror_export_path(self, working_directory: Path, export_path: Path, suffix: str = "") -> Path:
		file_path = self.src
		rel_path = file_path.relative_to(working_directory)
		dash = f"-{suffix}" if suffix else ""
		return export_path / rel_path.parent / f"{self.table.id}{dash}.json"
	
	def export_symbols(self, working_directory: Path, export_path: Path):
		output_path = self.mirror_export_path(working_directory, export_path, suffix="symbols")
		output_path.parent.mkdir(parents=True, exist_ok=True)
		self.table.export_to_json(output_path)

	def export_typeslots(self, working_directory: Path, export_path: Path):
		from typify.preprocessing.instance_utils import ReferenceSet
		from typify.preprocessing.precollector import PreCollector
		from typify.inferencing.commons import Typing, Checker
		from typify.inferencing.expression import TypeExpr

		output_path = self.mirror_export_path(working_directory, export_path, suffix="types")
		output_path.parent.mkdir(parents=True, exist_ok=True)

		data = {
			"variables": {
				"meta": {
					"total": 0,
					"typed": 0
				}
			},
			"functions": {
				"meta": {
					"total": 0,
					"typed": 0
				}
			}
		}

		for key, value in self.vslots.items():
			value[1] = value[1].as_type() if isinstance(value[1], ReferenceSet) else value[1]

			k = f"{key[0]}:{key[1]}"
			v = f"{value[0]}: {value[1]}"
			data["variables"][k] = v
			data["variables"]["meta"]["total"] += 1

			is_any = isinstance(value[1], TypeExpr) and Checker.match_origin(value[1].base, Typing.get_type("Any"))
			is_unvisited = value[1] == PreCollector.UNVISITED

			if not is_any and not is_unvisited:
				data["variables"]["meta"]["typed"] += 1

		for key, value in self.fslots.items():
			k = f"{key[0]}:{key[1]}"

			for x, y in value[2].items():
				value[2][x] = repr(y.as_type()) if isinstance(value[2][x], ReferenceSet) else value[2][x]
			
			value[3] = repr(value[3].as_type()) if isinstance(value[3], ReferenceSet) else value[3]
			
			v = PreCollector.build_function_signature(value[0], value[1], value[2], value[3])
			data["functions"][k] = v
			data["functions"]["meta"]["total"] += 1

			return_is_any = isinstance(value[3], TypeExpr) and Checker.match_origin(value[3].base, Typing.get_type("Any"))
			return_is_unvisited = value[3] == PreCollector.UNVISITED
			
			if not return_is_any and not return_is_unvisited:
				data["functions"]["meta"]["typed"] += 1
			
			for t in value[2].values():
				data["functions"]["meta"]["total"] += 1

				is_any = isinstance(t, TypeExpr) and Checker.match_origin(t.base, Typing.get_type("Any"))
				is_unvisited = t == PreCollector.UNVISITED
				
				if not is_any and not is_unvisited:
					data["functions"]["meta"]["typed"] += 1

		with output_path.open("w", encoding="utf-8") as f:
			json.dump(data, f, indent=4)


