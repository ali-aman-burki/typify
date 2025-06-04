from src.preprocessing.module_meta import ModuleMeta
from src.call_utils import CallUtils
from src.annotation_types import UnresolvedType

import ast
import copy

class SlotsCollector(ast.NodeVisitor):
	def __init__(self, module_meta: ModuleMeta):
		self.module_meta = module_meta
		self.vslots = self.module_meta.vslots
		self.fslots = self.module_meta.fslots
	
	def process_target(self, target: ast.AST):
		if isinstance(target, (ast.Tuple, ast.List)):
			for elt in target.elts: self.process_target(elt)
		else:
			key = (target.lineno, target.col_offset)
			value = (ast.unparse(target), UnresolvedType(None))
			self.vslots[key] = value

	def visit_FunctionDef(self, node):
		key = (node.lineno, node.col_offset)
		value = (node.name, CallUtils.build_parameter_map(node), UnresolvedType(None))
		self.fslots[key] = value
		self.generic_visit(node)
	
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