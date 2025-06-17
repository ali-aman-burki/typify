import ast
import copy

from src.symbol_table import (
	Table,
	ClassTable,
	VariableTable,
	DefinitionTable,
)
from src.preprocessing.module_meta import ModuleMeta
from src.preprocessing.scope_manager import ScopeManager
from src.function_utils import FunctionUtils
from src.preloading.commons import AnyType

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
		self.symbols: set[Table] = set()

	def visit_Import(self, node):
		self.imports.append((node, self.current_table.get_latest_definition(), self.function_depth!=0))
		self.generic_visit(node)
	
	def visit_ImportFrom(self, node):
		self.imports.append((node, self.current_table.get_latest_definition(), self.function_depth!=0))
		self.generic_visit(node)

	def visit_ClassDef(self, node):
		enclosing = self.current_table.get_latest_definition()
		self.push(ScopeManager.class_table(node, enclosing, self.module_table, self.symbols))
		self.generic_visit(node)
		self.pop()

	def visit_FunctionDef(self, node):
		parameters = FunctionUtils.collect_parameters(node, self.module_table)
		key = (node.lineno, node.col_offset)
		value = (node.name, parameters, AnyType)
		self.fslots[key] = value

		enclosing = self.current_table.get_latest_definition()
		fdef = self.push(ScopeManager.function_table(node, enclosing, self.module_table, self.symbols))
		for var in parameters.values(): self.symbols.add(fdef.add_variable(var))

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
		enclosing = self.current_table.get_latest_definition()
		position = (name_node.lineno, name_node.col_offset)
		var = VariableTable(name_node.id)
		var.add_definition(DefinitionTable(self.module_table, position))
		var = enclosing.add_variable(var)
		self.symbols.add(var)

		if isinstance(self.current_table, ClassTable):
			grandparent = self.current_table.parent
			cvar = grandparent.variables[self.current_table.key]
			for pt in cvar.points_to: pt.add_variable(var)

	def process_target(self, target: ast.AST):
		if isinstance(target, (ast.Tuple, ast.List)):
			for elt in target.elts:
				self.process_target(elt)
		else:
			key = (target.lineno, target.col_offset)
			value = (ast.unparse(target), AnyType)
			self.vslots[key] = value

			if isinstance(target, ast.Name):
				self.process_variable(target)