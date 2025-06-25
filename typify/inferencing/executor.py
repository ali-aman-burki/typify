import ast
import copy

from typify.inferencing.commons import (
    Context,
	Builtins
)
from typify.inferencing.typeutils import (
    TypeUtils, 
    TypeExpr
)
from typify.preprocessing.symbol_table import (
	 ModuleTable,
	 NameTable,
	 InstanceTable,
	 DefinitionTable,
	 Table,
	 ClassTable,
	 FunctionTable
)

class Executor(ast.NodeVisitor):
	def __init__(
			  self, 
			  context: Context,
			  symbol: Table,
			  namespace: InstanceTable, 
			  tree: ast.AST,
			  snapshot_log: list[set[str]] = None
		):
		self.context = context
		self.symbol = symbol
		self.namespace = namespace
		self.tree = tree
		self.snapshot_log = snapshot_log

	def execute(self): self.visit(self.tree)
	def snapshot(self): return [s.copy() for s in self.snapshot_log]

	def add_to_snapshot(self, points_to: set[InstanceTable]):
		immutable = {pt.key for pt in points_to}
		self.snapshot_log.append(immutable)

	def visit_ClassDef(self, class_tree: ast.ClassDef):
		name = class_tree.name
		position = (class_tree.lineno, class_tree.col_offset)
		defkey = (self.context.module_meta.table, position)
		namedef = self.process_name(name, defkey)

		class_table = ClassTable(name)
		entering_symbol = class_table.add_definition(DefinitionTable(defkey))
		self.symbol.merge_class(class_table)
		
		entering_namespace = TypeUtils.instantiate(Builtins.get_type("type"))
		entering_namespace.origin = entering_symbol
		namedef.points_to.add(entering_namespace)
		self.add_to_snapshot(namedef.points_to)
	
		Executor(
			self.context, 
			entering_symbol, 
			entering_namespace, 
			ast.Module(class_tree.body, type_ignores=[]),
			self.snapshot_log
		).execute()
	
	def visit_FunctionDef(self, func_tree: ast.FunctionDef):
		name = func_tree.name
		position = (func_tree.lineno, func_tree.col_offset)
		defkey = (self.context.module_meta.table, position)
		namedef = self.process_name(name, defkey)

		function_table = FunctionTable(name)
		fdef = function_table.add_definition(DefinitionTable(defkey))
		self.symbol.merge_function(function_table)

		func_type = TypeUtils.instantiate(Builtins.get_type("function"))
		namedef.points_to.add(func_type)
		func_type.origin = fdef
		self.add_to_snapshot(namedef.points_to)
	
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

	def process_name(self, name: str, defkey: tuple[ModuleTable, tuple[int, int]]):
		nametable = NameTable(name)
		namedef = nametable.add_definition(DefinitionTable(defkey))
		self.namespace.merge_name(nametable)
		self.symbol.merge_name(nametable)
		return namedef
	
	def process_target(self, target: ast.AST):
		if isinstance(target, (ast.Tuple, ast.List)):
			for elt in target.elts:
				self.process_target(elt)
		else:
			position = (target.lineno, target.col_offset)
			defkey = (self.context.module_meta.table, position)
			if isinstance(target, ast.Name):
				namedef = self.process_name(target.id, defkey)
				self.symbol.merge_name(namedef.parent)
