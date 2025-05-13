from src.builtins_ctn import *
from src.contanier_types import *
from src.symbol_table import Table

class Context:
	def __init__(self, library_table: Table, module_table: Table, current_table: Table):
		self.library_table = library_table
		self.module_table = module_table
		self.current_table = current_table

	def resolve(self, node: ast.AST):
		if isinstance(node, ast.Constant):
			return Type(builtins.classes[type(node.value).__name__])
		elif isinstance(node, ast.List):
			element_types = [self.resolve(el) for el in node.elts]
			return ListType(TypeAnnotation.unify(element_types))
		elif isinstance(node, ast.Set):
			element_types = [self.resolve(el) for el in node.elts]
			return SetType(TypeAnnotation.unify(element_types))
		elif isinstance(node, ast.Tuple):
			element_types = [self.resolve(el) for el in node.elts]
			return TupleType(element_types)
		elif isinstance(node, ast.Dict):
			key_type = TypeAnnotation.unify([self.resolve(k) for k in node.keys if k is not None])
			value_type = TypeAnnotation.unify([self.resolve(v) for v in node.values if v is not None])
			return DictType(key_type, value_type)
		return None
