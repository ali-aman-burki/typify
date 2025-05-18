from src.builtins_ctn import builtins
from src.contanier_types import *
import ast

class AnnotationConverter(ast.NodeVisitor):
	def visit_Name(self, node):
		if node.id in builtins.classes:
			return Type(builtins.classes[node.id])
		return UnresolvedType(node)

	def visit_Constant(self, node):
		return Type(builtins.classes[type(node.value).__name__])

	def visit_Attribute(self, node):
		return UnresolvedType(node)

	def visit_Subscript(self, node):
		base = self.visit(node.value)

		slice_node = node.slice
		if isinstance(slice_node, ast.Tuple):
			args = [self.visit(elt) for elt in slice_node.elts]
		else:
			args = [self.visit(slice_node)]

		if isinstance(base, UnresolvedType):
			name = ast.unparse(node.value)
			if name == "list":
				return ListType(args[0])
			elif name == "set":
				return SetType(args[0])
			elif name == "tuple":
				return TupleType(args)
			elif name == "dict":
				return DictType(args[0], args[1])
			elif name == "Union":
				return UnionType(args)
			elif name == "Optional":
				return OptionalType(args[0])
			else:
				return UnresolvedType(node)
		
		return UnresolvedType(node)

	def visit_BinOp(self, node):
		if isinstance(node.op, ast.BitOr):
			left = self.visit(node.left)
			right = self.visit(node.right)

			def flatten_union(node):
				if isinstance(node, UnionType):
					return node.types
				return [node]

			return UnionType(flatten_union(left) + flatten_union(right))

		return UnresolvedType(node)

	def visit(self, node):
		if node is None:
			return AnyType()
		return super().visit(node)
