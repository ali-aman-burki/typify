from src.symbol_table import Table, ModuleTable, VariableTable, PackageTable, LibraryTable
from src.typeutils import TypeExpr

from pathlib import Path

import ast
import json

class ModuleMeta:

	def __init__(self, src_path: Path, table: ModuleTable, library_table: LibraryTable):
		self.src_path = src_path
		self.tree: ast.AST = None
		self.table = table
		self.library_table = library_table
		self.imports: list[tuple[ast.AST, Table, bool]] = []
		self.vslots: dict[tuple[int, int], tuple[str, TypeExpr]] = {}
		self.fslots: dict[tuple[int, int], tuple[str, dict[str, VariableTable], TypeExpr]] = {}
		self.is_stub = src_path.suffix == ".pyi"
		self.trust_annotations = False

	def load_tree(self):
		if not self.tree:
			with open(self.src_path, "r", encoding="utf-8") as file:
				source_code = file.read()
			self.tree = ast.parse(source_code)

	def __repr__(self):
		return self.table.fqn

	@staticmethod
	def from_source(src_path: Path, library_table: Table):
		return ModuleMeta(src_path, ModuleTable(src_path.stem), library_table)
	
	def mirror_export_path(self, working_directory: Path, export_path: Path, suffix: str = "") -> Path:
		file_path = self.src_path
		rel_path = file_path.relative_to(working_directory)
		dash = f"-{suffix}" if suffix else ""
		return export_path / rel_path.parent / f"{self.table.key}{dash}.json"
	
	def export_symbols(self, working_directory: Path, export_path: Path):
		output_path = self.mirror_export_path(working_directory, export_path, suffix="symbols")
		output_path.parent.mkdir(parents=True, exist_ok=True)
		self.table.export_to_json(output_path)

	def export_typeslots(self, working_directory: Path, export_path: Path):
		output_path = self.mirror_export_path(working_directory, export_path, suffix="types")
		output_path.parent.mkdir(parents=True, exist_ok=True)

		output = {
			"vdefs": {
				f"{k[0]}:{k[1]}": f"{v[0]}: {v[1]}" for k, v in self.vslots.items()
			},
			"fdefs": {
				f"{k[0]}:{k[1]}": f"def {v[0]}(...) -> {v[2]}" for k, v in self.fslots.items()
			}
		}

		with output_path.open("w", encoding="utf-8") as f:
			json.dump(output, f, indent="\t")

