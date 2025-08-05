from __future__ import annotations

import ast

from typify.preprocessing.instance_utils import Instance, ReferenceSet
from typify.preprocessing.precollector import PreCollector
from typify.preprocessing.symbol_table import ClassDefinition
from typify.inferencing.commons import (
    Checker,
    Typing,
	Builtins
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
			else: prefix = repr(self.base)

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
	def annotation_to_typeexpr(
		annotation: Instance, 
		concsubs: dict
	) -> TypeExpr:
		
		from typify.inferencing.generics.model import Placeholder
		
		concsubs: dict[Placeholder, TypeExpr | list[TypeExpr]] = concsubs
		
		if Checker.is_generic_alias(annotation):
			return AliasParser.resolve_type_expr(annotation.packed_expr, concsubs)
		elif Checker.is_typevar(annotation):
			for k, v in concsubs.items():
				if k.typevar == annotation:
					if v: return v
			return TypeExpr(Typing.get_type("Any"))
		elif Checker.is_type(annotation):
			return TypeExpr(annotation.origin)
		elif annotation.instanceof(Builtins.get_type("NoneType")):
			return TypeExpr(Builtins.get_type("NoneType"))
		else:
			return TypeExpr(Typing.get_type("Any"))

	@staticmethod
	def resolve_type_expr(
		packed_expr: PackedExpr, 
		concsubs: dict
	) -> TypeExpr | list[TypeExpr]:
		
		from typify.inferencing.generics.model import Placeholder
		
		concsubs: dict[Placeholder, TypeExpr | list[TypeExpr]] = concsubs

		if Checker.is_type(packed_expr.base):
			targs: list[TypeExpr] = []

			if Checker.match_origin(
				packed_expr.base.origin, 
				Typing.get_type("Unpack")
			):
				tvt = packed_expr.args[0].base
				for k, v in concsubs.items():
					if k.typevar == tvt:
						return v
				return []

			for parg in packed_expr.args:
				result = AliasParser.resolve_type_expr(parg, concsubs)
				if isinstance(result, list):
					targs.extend(result)
				else:
					targs.append(result)
			return TypeExpr(packed_expr.base.origin, targs)
		elif Checker.is_typevar(packed_expr.base):
			tv = packed_expr.base
			for k, v in concsubs.items():
				if k.typevar == tv:
					return v
			return TypeExpr(Typing.get_type("Any"))
		elif packed_expr.base.instanceof(Builtins.get_type("NoneType")):
			return TypeExpr(Builtins.get_type("NoneType"))
		else:
			return TypeExpr(Typing.get_type("Any"))

	#TODO: may need to later uncomment. so far no evidence of incorrect output if not uncommented
	@staticmethod
	def get_packed_expr(resolver, elt: ast.Expr):
		from typify.inferencing.resolver import Resolver

		resolver: Resolver = resolver
		relt = resolver.resolve_value(elt)
		if relt: 
			relt = relt.ref()
			# if Checker.is_generic_alias(relt):
			# 	return relt.packed_expr
			# else:
			return PackedExpr(relt)
		return None

	@staticmethod
	def attach(
		resolver, 
		node: ast.Subscript,
		base_inst: Instance,
		genref: Instance, 
	) -> ReferenceSet:
		from typify.inferencing.resolver import Resolver

		resolver: Resolver = resolver
		
		args = []
		
		if isinstance(node.slice, ast.Tuple):
			for elt in node.slice.elts:
				resolved = AliasParser.get_packed_expr(resolver, elt)
				if resolved: args.append(resolved)
		else:
			resolved = AliasParser.get_packed_expr(resolver, node.slice)
			if resolved: args.append(resolved)

		genref.packed_expr = PackedExpr(base_inst, args)