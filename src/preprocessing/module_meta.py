from src.symbol_table import Table, ModuleTable
from pathlib import Path

import ast

class ModuleMeta:

	def __init__(self, src_path: Path, ast_rep: ast.AST, table: ModuleTable, library_table: Table):
		self.src_path = src_path
		self.ast_rep = ast_rep
		self.table = table
		self.library_table = library_table
		self.dependency_map: dict[str, list[tuple[list[ModuleMeta], int]]] = {}
		self.dependencies: set[ModuleMeta] = set()

	def __str__(self):
		return self.table.fully_qualified_name()

	@staticmethod
	def from_source(src_path: Path, library_table: Table):
		with open(src_path, "r", encoding="utf-8") as file:
			source_code = file.read()
		ast_rep = ast.parse(source_code)
		table = ModuleTable(src_path.stem)
		meta = ModuleMeta(src_path, ast_rep, table, library_table)
		return meta