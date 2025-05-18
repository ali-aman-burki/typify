from src.builtins_ctn import builtins
from src.symbol_table import Table, VariableTable
from src.contanier_types import *
from src.typeutils import TypeUtils
import ast

class Context:
	def __init__(self, library_table: Table, module_table: Table, current_table: Table):
		self.library_table = library_table
		self.module_table = module_table
		self.current_table = current_table

	def lookup(self, identifier: str):

		pass

	def verify_lhs(self, node: ast.AST):
		if isinstance(node, ast.Name):
			name = node.id
			if name not in self.current_table.get_latest_definition().variables:
				self.current_table.get_latest_definition().add_variable(VariableTable(name))
			return self.current_table.get_latest_definition().variables[name]
		return None

	def resolve_type(self, node: ast.AST):
		if isinstance(node, ast.Constant):
			return Type(builtins.classes[type(node.value).__name__])
		elif isinstance(node, ast.JoinedStr):
			return Type(builtins.classes["str"])
		elif isinstance(node, ast.BoolOp):
			return Type(builtins.classes["bool"])
		elif isinstance(node, ast.List):
			element_types = [self.resolve_type(el) for el in node.elts]
			return ListType(TypeUtils.unify(element_types))
		elif isinstance(node, ast.Set):
			element_types = [self.resolve_type(el) for el in node.elts]
			return SetType(TypeUtils.unify(element_types))
		elif isinstance(node, ast.Tuple):
			element_types = [self.resolve_type(el) for el in node.elts]
			return TupleType(element_types)
		elif isinstance(node, ast.Dict):
			key_type = TypeUtils.unify([self.resolve_type(k) for k in node.keys if k is not None])
			value_type = TypeUtils.unify([self.resolve_type(v) for v in node.values if v is not None])
			return DictType(key_type, value_type)
		elif isinstance(node, ast.Name):
			pass
		elif isinstance(node, ast.Call):
			pass
		elif isinstance(node, ast.Attribute):
			pass

		return UnresolvedType(node)
