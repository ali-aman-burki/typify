from src.builtins_ctn import *
from src.contanier_types import *
from src.symbol_table import Table

class Context:
	def __init__(self, library_table: Table, module_table: Table, current_table: Table):
		self.library_table = library_table
		self.module_table = module_table
		self.current_table = current_table

	def build_chain(self, node: ast.AST):
		chain = []
		while True:
			if isinstance(node, ast.Attribute):
				chain.append(node)
				node = node.value
			elif isinstance(node, ast.Call):
				chain.append(node)
				node = node.func
			elif isinstance(node, ast.Subscript):
				chain.append(node)
				break
			elif isinstance(node, ast.Name):
				chain.append(node)
				break
			else:
				chain.append(node)
				break
		return list(reversed(chain))

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
		elif isinstance(node, ast.List):
			element_types = [self.resolve_type(el) for el in node.elts]
			return ListType(TypeAnnotation.unify(element_types))
		elif isinstance(node, ast.Set):
			element_types = [self.resolve_type(el) for el in node.elts]
			return SetType(TypeAnnotation.unify(element_types))
		elif isinstance(node, ast.Tuple):
			element_types = [self.resolve_type(el) for el in node.elts]
			return TupleType(element_types)
		elif isinstance(node, ast.Dict):
			key_type = TypeAnnotation.unify([self.resolve_type(k) for k in node.keys if k is not None])
			value_type = TypeAnnotation.unify([self.resolve_type(v) for v in node.values if v is not None])
			return DictType(key_type, value_type)
		else:
			chain = self.build_chain(node)
			for n in chain:
				if isinstance(n, ast.Name):
					print(f"Name: {n.id}")
				elif isinstance(n, ast.Call):
					print(f"Call: ()")
				elif isinstance(n, ast.Attribute):
					print(f"Attr: {n.attr}")
				elif isinstance(n, ast.Subscript):
					print(f"Subscript: (skipping deeper traversal)")
				else:
					print(f"Other: {ast.dump(n)}")
			return None
