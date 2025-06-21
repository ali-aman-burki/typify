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

	def to_absolute_name(self, import_module: str | None, level: int) -> str:
		if not level: return import_module

		import_module = import_module if import_module else ""
		import_chain = import_module.split(".")
		path_chain = self.table.get_path_chain() 
		current = path_chain[-level]
		result = []
		for i in import_chain[:-1]:
			current = current.packages[i]
		
		for table in path_chain:
			result.append(table.key)
			if table == current: break

		return ".".join(result)

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

