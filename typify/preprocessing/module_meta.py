from pathlib import Path
import ast, json

from typify.preprocessing.symbol_table import ModuleTable

class ModuleMeta:

	def __init__(self, src: Path, trust_annotations: bool):
		from typify.inferencing.typeutils import TypeExpr

		self.src = src
		self.tree: ast.AST = None
		self.table = ModuleTable(src.stem)
		self.trust_annotations = trust_annotations

		self.vslots: dict[tuple[int, int], tuple[ast.Expr, TypeExpr]] = {}
		self.fslots: dict[tuple[int, int], list[ast.FunctionDef | dict[str, TypeExpr] | TypeExpr]] = {}

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
		return export_path / rel_path.parent / f"{self.table.key}{dash}.json"
	
	def export_symbols(self, working_directory: Path, export_path: Path):
		output_path = self.mirror_export_path(working_directory, export_path, suffix="symbols")
		output_path.parent.mkdir(parents=True, exist_ok=True)
		self.table.export_to_json(output_path)


	def export_typeslots(self, working_directory: Path, export_path: Path):
		from typify.preprocessing.precollector import PreCollector

		output_path = self.mirror_export_path(working_directory, export_path, suffix="types")
		output_path.parent.mkdir(parents=True, exist_ok=True)

		data = {
			"variables": {},
			"functions": {}
		}

		for key, value in self.vslots.items():
			k = f"{key[0]}:{key[1]}"
			v = f"{ast.unparse(value[0])}: {value[1]}"
			data["variables"][k] = v

		for key, value in self.fslots.items():
			k = f"{key[0]}:{key[1]}"
			v = PreCollector.build_function_signature(value[0], value[1], value[2])
			data["functions"][k] = v

		with output_path.open("w", encoding="utf-8") as f:
			json.dump(data, f, indent=4)


