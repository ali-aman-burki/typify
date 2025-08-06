from pathlib import Path
import ast, json

from typify.preprocessing.symbol_table import Module

class ModuleMeta:

	def __init__(self, src: Path, trust_annotations: bool):
		from typify.preprocessing.instance_utils import ReferenceSet

		self.src = src
		self.tree: ast.Module = None
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

	def typeslots(self):
		from typify.preprocessing.instance_utils import ReferenceSet
		from typify.preprocessing.precollector import PreCollector

		data = {
			"variables": {},
			"functions": {}
		}

		for key, value in self.vslots.items():
			value[1] = value[1].as_type().strip() if isinstance(value[1], ReferenceSet) else value[1]
			k = f"{value[2]}:{key[0]}:{key[1]}"
			v = f"{value[0]}: {value[1]}"
			data["variables"][k] = v

		for key, value in self.fslots.items():
			k = f"{value[4]}:{key[0]}:{key[1]}"

			for x, y in value[2].items():
				value[2][x] = repr(y.as_type().strip()) if isinstance(value[2][x], ReferenceSet) else value[2][x]
			
			value[3] = repr(value[3].as_type().strip()) if isinstance(value[3], ReferenceSet) else value[3]
			
			v = PreCollector.build_function_signature(value[0], value[1], value[2], value[3])
			data["functions"][k] = v
			
		return data


