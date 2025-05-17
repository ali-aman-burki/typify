from src.builtins_ctn import *
from src.contanier_types import *
from src.symbol_table import Table
from src.chain import Chain

class Context:
	def __init__(self, library_table: Table, module_table: Table, current_table: Table):
		self.library_table = library_table
		self.module_table = module_table
		self.current_table = current_table

	def build_chain(self, node: ast.AST):
		raw_chain = []
		while True:
			if isinstance(node, ast.Attribute):
				raw_chain.append(node)
				node = node.value
			elif isinstance(node, ast.Call):
				raw_chain.append(node)
				node = node.func
			elif isinstance(node, ast.Subscript):
				raw_chain.append(node)
				node = node.value
			elif isinstance(node, ast.Name):
				raw_chain.append(node)
				break
			else:
				raw_chain.append(node)
				break
		raw_chain = list(reversed(raw_chain))
		processed_chain = []
		attribute_indices = []
		for i in range(len(raw_chain)):
			n = raw_chain[i]
			if isinstance(n, ast.Name): attribute_indices.append(i)
			if isinstance(n, ast.Attribute): attribute_indices.append(i)

		for i in range(len(attribute_indices)):
			current_index = attribute_indices[i]
			next_index = attribute_indices[i + 1] if i + 1 < len(attribute_indices) else len(raw_chain)
			processed_chain.append([])
			for j in range(current_index, next_index):
				processed_chain[i].append(raw_chain[j])

		return processed_chain


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
			print(Chain(node))
			return None
