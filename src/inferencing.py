import ast
from src.symbol_table import *
from src.context import Context
from src.annotation_parser import AnnotationParser
from src.contanier_types import Type
from src.builtins_ctn import builtins
from src.typeutils import TypeUtils
from src.preprocessing.module_meta import ModuleMeta

import json
import copy
from pathlib import Path

class Inferencer(ast.NodeVisitor):
	def __init__(self, module_meta: ModuleMeta):
		self.library_table = module_meta.library_table
		self.module_table = module_meta.table
		self.current_table = module_meta.table

		self.type_data = {
			"vassignments": {},
			"functions": {}
		}

	def visit_Import(self, node):
		self.current_table.get_latest_definition().imports.append(node)
		self.generic_visit(node)

	def visit_ImportFrom(self, node):
		self.current_table.get_latest_definition().imports.append(node)
		self.generic_visit(node)

	def visit_ClassDef(self, node):
		self.generic_visit(node)

	def visit_AsyncFunctionDef(self, node):
		self.visit_FunctionDef(node)

	def visit_FunctionDef(self, node):
		self.generic_visit(node)

	def visit_Return(self, node):
		self.generic_visit(node)

	def visit_Global(self, node):
		self.current_table.globals.update(node.names)
		self.generic_visit(node)

	def visit_Nonlocal(self, node):
		self.current_table.nonlocals.update(node.names)
		self.generic_visit(node)

	def visit_Call(self, node):
		self.generic_visit(node)

	def visit_AnnAssign(self, node):
		self.generic_visit(node)

	def visit_Assign(self, node):
		self.generic_visit(node)
	
	def visit_AugAssign(self, node):
		toAssign = ast.Assign(
			targets=[node.target],
			value=ast.BinOp(
				left=copy.deepcopy(node.target),
				op=node.op,
				right=node.value
			)
		)
		ast.copy_location(toAssign, node)
		ast.copy_location(toAssign.value, node)

		toAssign = ast.fix_missing_locations(toAssign)

		self.visit_Assign(toAssign)

	def export_type_data(self, directory: Path, file_name: str):
		directory.mkdir(parents=True, exist_ok=True)
		file_path = directory / f"{file_name}.json"
		output_data = {
			"vassignments": {},
			"functions": {}
		}
		for key, value in self.type_data["vassignments"].items():
			lhs = ast.unparse(value[0]) 
			inf_type = value[1]
			output_data["vassignments"][f"{key[0]}:{key[1]}"] = f"{lhs}: {inf_type}"
		
		for key, value in self.type_data["functions"].items():
			func_name, func_type = value
			output_data["functions"][f"{key[0]}:{key[1]}"] = f"{func_name}() -> {func_type}"
		with file_path.open("w", encoding="utf-8") as f:
			json.dump(output_data, f, indent='\t')
