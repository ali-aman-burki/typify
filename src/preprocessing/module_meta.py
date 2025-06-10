from src.symbol_table import Table, ModuleTable, VariableTable
from src.typeutils import TypeAnnotation
from src.call_utils import ParameterSpec
from pathlib import Path

import ast
import json

class ModuleMeta:

	def __init__(self, src_path: Path, tree: ast.AST, table: ModuleTable, library_table: Table):
		self.src_path = src_path
		self.tree = tree
		self.table = table
		self.library_table = library_table
		self.imports: list[tuple[ast.AST, Table, bool]] = []
		self.dependency_map: dict[str, set[VariableTable]] = {}
		self.dependencies: set[ModuleMeta] = set()
		self.vslots: dict[tuple[int, int], tuple[str, TypeAnnotation]] = {}
		self.fslots: dict[tuple[int, int], tuple[str, dict[str, VariableTable], TypeAnnotation]] = {}

	def __repr__(self):
		return self.table.fully_qualified_name()

	@staticmethod
	def from_source(src_path: Path, library_table: Table):
		with open(src_path, "r", encoding="utf-8") as file:
			source_code = file.read()
		tree = ast.parse(source_code)
		table = ModuleTable(src_path.stem)
		meta = ModuleMeta(src_path, tree, table, library_table)
		return meta
	
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
			"dependency_map": {
				
			},
			"vdefs": {
				f"{k[0]}:{k[1]}": f"{v[0]}: {v[1]}" for k, v in self.vslots.items()
			},
			"fdefs": {
				f"{k[0]}:{k[1]}": f"def {v[0]}(...) -> {v[2]}" for k, v in self.fslots.items()
			}
		}
		
		for k, s in self.dependency_map.items():
			key = k
			formatted_list = [var.key for var in s]
			output["dependency_map"][key] = ", ".join(formatted_list)

		with output_path.open("w", encoding="utf-8") as f:
			json.dump(output, f, indent="\t")

