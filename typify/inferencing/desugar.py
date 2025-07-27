import ast

from typify.inferencing.resolver import Resolver

class Desugar:

	operator_to_dunder: dict[type[ast.AST], str | tuple[str]] = {
		ast.Add: ("__add__", "__radd__"),
		ast.Sub: ("__sub__", "__rsub__"),
		ast.Mult: ("__mul__", "__rmul__"),
		ast.MatMult: ("__matmul__", "__rmatmul__"),
		ast.Div: ("__truediv__", "__rtruediv__"),
		ast.FloorDiv: ("__floordiv__", "__rfloordiv__"),
		ast.Mod: ("__mod__", "__rmod__"),
		ast.Pow: ("__pow__", "__rpow__"),
		ast.LShift: ("__lshift__", "__rlshift__"),
		ast.RShift: ("__rshift__", "__rrshift__"),
		ast.BitAnd: ("__and__", "__rand__"),
		ast.BitOr: ("__or__", "__ror__"),
		ast.BitXor: ("__xor__", "__rxor__"),

		ast.UAdd: "__pos__",
		ast.USub: "__neg__",
		ast.Invert: "__invert__",

		ast.Eq: "__eq__",
		ast.NotEq: "__ne__",
		ast.Lt: "__lt__",
		ast.LtE: "__le__",
		ast.Gt: "__gt__",
		ast.GtE: "__ge__",
}

	@staticmethod
	def to_dunder(expr: ast.expr, use_reverse: bool = False) -> ast.Call:
		if isinstance(expr, ast.BinOp):
			op_type = type(expr.op)
			dunders = Desugar.operator_to_dunder.get(op_type)
			if not dunders:
				raise ValueError(f"No dunder mapping for binary operator {op_type}")

			forward_dunder, reverse_dunder = dunders

			if use_reverse:
				dunder_name = reverse_dunder
				left, right = expr.right, expr.left
			else:
				dunder_name = forward_dunder
				left, right = expr.left, expr.right

			func = ast.Attribute(value=left, attr=dunder_name, ctx=ast.Load())
			return ast.Call(func=func, args=[right], keywords=[])

		elif isinstance(expr, ast.UnaryOp):
			op_type = type(expr.op)
			dunder_name = Desugar.operator_to_dunder.get(op_type)
			if not dunder_name:
				raise ValueError(f"No dunder mapping for unary operator {op_type}")

			func = ast.Attribute(value=expr.operand, attr=dunder_name, ctx=ast.Load())
			return ast.Call(func=func, args=[], keywords=[])

		else:
			raise TypeError(f"Unsupported expr type: {type(expr)}")

	@staticmethod
	def subscript(node: ast.Subscript, use_class_getitem: bool) -> ast.Call:
		if not isinstance(node, ast.Subscript):
			raise TypeError("Expected ast.Subscript node")
		method = "__class_getitem__" if use_class_getitem else "__getitem__"
		return ast.Call(
			func=ast.Attribute(
				value=node.value,
				attr=method,
				ctx=ast.Load()
			),
			args=[node.slice],
			keywords=[]
		)

	@staticmethod
	def resolve(node: ast.expr, resolver: Resolver):
		from typify.preprocessing.instance_utils import ReferenceSet
		from typify.inferencing.expression import AliasParser
		from typify.inferencing.commons import Builtins, Checker
		from typify.inferencing.call_dispatcher import CallDispatcher

		if isinstance(node, ast.Subscript):
			baseset = resolver.resolve_value(node.value)
			result = ReferenceSet()
			for base in baseset:
				if base.instanceof(Builtins.get_type("type")):
					processed_node = Desugar.subscript(node, True)
					dispatcher = CallDispatcher(resolver, processed_node)
					
					genset = dispatcher.dispatch()
					if genset:
						genref = genset.ref()
						result.add(genref)
						if Checker.is_generic_alias(genref):
							AliasParser.attach(
								resolver, 
								node, 
								base, 
								genref
							)
				else:
					processed_node = Desugar.subscript(node, False)
					dispatcher = CallDispatcher(resolver, processed_node)
					refset = dispatcher.dispatch()
					result.update(refset)

			return result
		
		elif isinstance(node, ast.BinOp):
			desugared = Desugar.to_dunder(node)
			dispatcher = CallDispatcher(resolver, desugared)
			refset = dispatcher.dispatch()

			if not refset:
				desugared = Desugar.to_dunder(node, True)
				dispatcher = CallDispatcher(resolver, desugared)
				refset = dispatcher.dispatch()
			
			return refset
		else:
			return ReferenceSet()