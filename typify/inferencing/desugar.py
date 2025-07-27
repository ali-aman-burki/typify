import ast

from typify.inferencing.resolver import Resolver

class Desugar:
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

		return ReferenceSet()