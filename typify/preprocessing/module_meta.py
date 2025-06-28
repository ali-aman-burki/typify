from typify.preprocessing.symbol_table import ModuleTable

from pathlib import Path

import ast

class ModuleMeta:

	def __init__(self, src: Path, trust_annotations: bool):
		self.src = src
		self.tree: ast.AST = None
		self.table = ModuleTable(src.stem)
		self.trust_annotations = trust_annotations

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
		pass

