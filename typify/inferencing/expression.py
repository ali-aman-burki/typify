from __future__ import annotations

import ast

from typify.preprocessing.instance_utils import Instance, ReferenceSet
from typify.preprocessing.precollector import PreCollector
from typify.preprocessing.symbol_table import ClassDefinition
from typify.inferencing.commons import (
    Builtins, 
    Typing,
)

class PackedExpr:

	def __init__(
			self,
			base: Instance,
			args: list[PackedExpr] = None
		):

		self.base = base
		self.args = args or []
	
	def __repr__(self):
		prefix = ""
		if self.base:
			if self.base.origin: prefix = self.base.origin.parent.id
			else: prefix = self.base.instantiator.parent.id

		fqn = prefix if prefix else PreCollector.UNVISITED
		strs = []
		for arg in self.args:
			strs.append(repr(arg))
		joined = ", ".join(strs)
		joined = f"[{joined}]" if joined else joined
		return fqn + f"{joined}"

class TypeExpr:

	def __init__(
			self, 
			base: ClassDefinition, 
			typeargs: list[TypeExpr] = None
		):
		self.base = base
		self.typeargs = typeargs or []

	def strip(self) -> TypeExpr:
		from typify.inferencing.commons import Checker, Typing

		new_args = [arg.strip() for arg in self.typeargs]

		if Checker.match_origin(self.base, Typing.get_type("Union")):
			new_args = [
				arg for arg in new_args
				if not Checker.match_origin(arg.base, Typing.get_type("Any"))
			]
			if not new_args:
				return TypeExpr(Typing.get_type("Any"))
			if len(new_args) == 1:
				return new_args[0]
			return TypeExpr(self.base, new_args)

		return TypeExpr(self.base, new_args)


	def __eq__(self, other: TypeExpr):
		if not isinstance(other, TypeExpr):
			return NotImplemented
		if self.base != other.base or len(self.typeargs) != len(other.typeargs):
			return False
		return all(a == b for a, b in zip(self.typeargs, other.typeargs))

	def __hash__(self):
		return hash((self.base, tuple(self.typeargs)))

	def __repr__(self):
		fqn = self.base.parent.id if self.base else PreCollector.UNVISITED
		strs = []
		for typeexpr in self.typeargs:
			strs.append(repr(typeexpr))
		joined = ", ".join(strs)
		joined = f"[{joined}]" if joined else joined
		return fqn + f"{joined}"
	
class AliasParser:
	
	@staticmethod
	def resolve_if_generic_alias(
		resolver, 
		base_set: ReferenceSet, 
		node: ast.Subscript
	) -> ReferenceSet:
		from typify.inferencing.typeutils import TypeUtils
		from typify.inferencing.resolver import Resolver

		resolver: Resolver = resolver

		def get_packed_expr(elt: ast.Expr):
			relt = resolver.resolve_value(elt)
			if relt: 
				relt = relt.ref()
				if relt.instanceof(Typing.get_type("_GenericAlias")):
					return relt.packed_expr
				else:
					return PackedExpr(relt)
			return None
		
		base_inst = base_set.ref()
		if base_inst.instanceof(Builtins.get_type("type")):
			base_inst = base_set.ref()
			args = []
			
			if isinstance(node.slice, ast.Tuple):
				for elt in node.slice.elts:
					resolved = get_packed_expr(elt)
					if resolved: args.append(resolved)
			else:
				resolved = get_packed_expr(node.slice)
				if resolved: args.append(resolved)

			ginstance = TypeUtils.instantiate_with_args(Typing.get_type("_GenericAlias"))
			ginstance.packed_expr = PackedExpr(base_inst, args)
			return ReferenceSet(ginstance)

		return ReferenceSet()