import ast
import copy

from src.symbol_table import (
	Table,
	VariableTable,
	DefinitionTable,
)
from src.preprocessing.module_meta import ModuleMeta
from src.preprocessing.scope_manager import ScopeManager
from src.annotation_types import UnresolvedType
from src.call_utils import CallUtils

class SymbolSlotCollector(ast.NodeVisitor):
	def __init__(self, module_meta: ModuleMeta):
		self.module_meta = module_meta
		self.library_table = module_meta.library_table
		self.module_table = module_meta.table
		self.current_table = self.module_table

		self.vslots = self.module_meta.vslots
		self.fslots = self.module_meta.fslots

		self.function_depth = 0
		self.imports = module_meta.imports

	def visit_Import(self, node):
		self.imports.append((node, self.current_table.get_latest_definition(), self.function_depth==0))
		self.generic_visit(node)
	
	def visit_ImportFrom(self, node):
		self.imports.append((node, self.current_table.get_latest_definition(), self.function_depth==0))
		self.generic_visit(node)

	def visit_ClassDef(self, node):
		enclosing = self.current_table.get_latest_definition()
		self.push(ScopeManager.class_table(node, enclosing))
		self.generic_visit(node)
		self.pop()

	def visit_FunctionDef(self, node):
		param_map = CallUtils.build_parameter_map(node)
		key = (node.lineno, node.col_offset)
		value = (node.name, param_map, UnresolvedType(None))
		self.fslots[key] = value

		enclosing = self.current_table.get_latest_definition()
		self.push(ScopeManager.function_table(node, enclosing))
		self.function_depth += 1
		self.generic_visit(node)
		self.function_depth -= 1
		self.pop()

	def visit_AsyncFunctionDef(self, node):
		return self.visit_FunctionDef(node)

	def visit_AnnAssign(self, node):
		self.process_target(node.target)
		self.generic_visit(node)

	def visit_Assign(self, node):
		for target in node.targets:
			self.process_target(target)
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

	def push(self, scope_def: Table):
		self.current_table = scope_def.get_enclosing_table()
		return scope_def

	def pop(self):
		self.current_table = self.current_table.get_enclosing_table()
		return self.current_table

	def process_variable(self, name_node: ast.Name):
		name = name_node.id
		position = (name_node.lineno, name_node.col_offset)
		if name not in self.current_table.get_latest_definition().variables:
			v = self.current_table.get_latest_definition().add_variable(VariableTable(name))
			v.add_definition(DefinitionTable(v.get_enclosing_module(), position))
		else:
			v = self.current_table.get_latest_definition().variables[name]
			v.add_definition(DefinitionTable(v.get_enclosing_module(), position))

	def process_target(self, target: ast.AST):
		if isinstance(target, (ast.Tuple, ast.List)):
			for elt in target.elts:
				self.process_target(elt)
		else:
			key = (target.lineno, target.col_offset)
			value = (ast.unparse(target), UnresolvedType(None))
			self.vslots[key] = value

			if isinstance(target, ast.Name):
				self.process_variable(target)