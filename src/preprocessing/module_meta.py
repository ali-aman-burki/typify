from src.symbol_table import Table, ModuleTable, VariableTable, PackageTable, LibraryTable
from src.typeutils import TypeExpr
from src.preloading.commons import builtin_lib, pystd_lib

from pathlib import Path

import ast
import json

class ModuleMeta:

	def __init__(self, src_path: Path, tree: ast.AST, table: ModuleTable, library_table: LibraryTable):
		self.src_path = src_path
		self.tree = tree
		self.table = table
		self.library_table = library_table
		self.imports: list[tuple[ast.AST, Table, bool]] = []
		self.dependency_map: dict[str, list[list[Table]]] = {}
		self.dependencies: set[ModuleMeta] = set()
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
		return self.table.fully_qualified_name()

	def resolve_chains(self, import_module: str) -> list[list[Table]]:
		path_chain = self.table.get_path_chain()
		import_chain = import_module.split(".")
		start_name = import_chain[0]
		starting_points: list[list[Table]] = []
		for i in range(len(path_chain)):
			table = path_chain[i]
			if start_name in table.modules:
				starting_points.append([table.modules[start_name]])
			elif start_name in table.packages: 
				starting_points.append([table.packages[start_name]])
		
		result: list[list[Table]] = []
		for starting_point in starting_points:
			current = starting_point[0]
			for j in range(1, len(import_chain)):
				if import_chain[j] in current.modules:
					current = current.modules[import_chain[j]]
					starting_point.append(current)
				elif import_chain[j] in current.packages:
					current = current.packages[import_chain[j]]
					starting_point.append(current)
			if len(starting_point) == len(import_chain):
				result.append(starting_point)
		
		if not result:
			if start_name in builtin_lib.modules: result.append([builtin_lib.modules[start_name]])

		if not result:
			if start_name in pystd_lib.modules:
				if start_name in pystd_lib.modules: result.append([pystd_lib.modules[start_name]])
			elif start_name in pystd_lib.packages:
				result.append([pystd_lib.packages[start_name]])
				current = result[0][0]
				for i in import_chain[1:]:
					if i in current.modules:
						current = current.modules[i]
						result[0].append(current)
					elif i in current.packages:
						current = current.packages[i]
						result[0].append(current)

		return result

	def filter_chains(self, chains: list[list[Table]]) -> list[list[Table]]:
		module_table = self.table
		new_chains = []

		for chain in chains:
			new_chain = []
			for table in chain:
				if isinstance(table, PackageTable) and "__init__" in table.modules and table.modules["__init__"] != module_table:
					new_chain.append(table.modules["__init__"])
				else:
					new_chain.append(table)
			new_chains.append(new_chain)
		return new_chains


	def collect_modules(self, resolved_chains: list[list[Table]]) -> set[Table]:
		modules: set[Table] = set()
		for chain in resolved_chains:
			for table in chain:
				if not isinstance(table, PackageTable): modules.add(table)
		return modules

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
		
		for k, l in self.dependency_map.items():
			key = k
			result = ', '.join('->'.join(x.key for x in sublist) for sublist in l)
			output["dependency_map"][key] = result

		with output_path.open("w", encoding="utf-8") as f:
			json.dump(output, f, indent="\t")

