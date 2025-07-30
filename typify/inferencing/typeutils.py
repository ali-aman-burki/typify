from __future__ import annotations

import ast

from typify.inferencing.commons import Typing, Checker
from typify.inferencing.expression import TypeExpr
from typify.preprocessing.instance_utils import (
	ReferenceSet,
	Instance
)
from typify.preprocessing.symbol_table import (
	ClassDefinition
)

class TypeUtils:

	@staticmethod
	def type_expr_from_refset(refset: ReferenceSet):
		type_exprs = []
		for ref in refset:
			type_exprs.append(ref.as_type())
		return TypeUtils.unify_from_exprs(type_exprs)

	@staticmethod
	def instantiate_from_type_expr(unified_type_expr: TypeExpr) -> ReferenceSet:
		if Checker.match_origin(unified_type_expr.base, Typing.get_type("Union")):
			result = ReferenceSet()
			for typeexpr in unified_type_expr.typeargs:
				result.update(TypeUtils.instantiate_from_type_expr(typeexpr))
			return result
		elif Checker.match_origin(unified_type_expr.base, Typing.get_type("Any")):
			return ReferenceSet()
		else:
			if not unified_type_expr.base: return ReferenceSet()

			instance = TypeUtils.instantiate_with_args(unified_type_expr.base, unified_type_expr.typeargs)
			init_method_name = instance.attribute_lookup("__init__")
			function_def = init_method_name.get_latest_definition().refset.ref()
			
			return ReferenceSet(instance)

	@staticmethod
	def unify_from_exprs(typeargs: list[TypeExpr] = None) -> TypeExpr:
		typeargs = typeargs or []
		typeargs = [item for item in typeargs if item.base is not None]
		union_def = Typing.get_type("Union")

		def flatten_recursive(
				types: list[TypeExpr], 
				seen: dict[TypeExpr, None]
			) -> None:
			for t in types:
				if t.base == union_def:
					flatten_recursive(t.typeargs, seen)
				else:
					seen[t] = None

		seen: dict[TypeExpr, None] = {}
		flatten_recursive(typeargs, seen)

		unique = list(seen.keys())

		if not unique:
			return TypeExpr(Typing.get_type("Any"))
		if len(unique) == 1:
			return unique[0]

		return TypeExpr(union_def, unique)

	@staticmethod
	def unify(refset: ReferenceSet):
		return TypeUtils.unify_from_exprs([ref.as_type() for ref in refset])

	@staticmethod
	def instantiate_with_args(
		instantiator: ClassDefinition, 
		typeargs: list[Instance] | None = None
		) -> Instance:
		
		instance = Instance(instantiator)
		instance.update_type_info(instantiator, typeargs)
		return instance

	@staticmethod
	def get_safe(lst, index, default=None):
		return lst[index] if 0 <= index < len(lst) else default
	
	@staticmethod
	def has_complete_return(stmts: list[ast.stmt]) -> bool:
		for stmt in stmts:
			if isinstance(stmt, ast.Return): return True
			elif isinstance(stmt, ast.If):
				then = TypeUtils.has_complete_return(stmt.body)
				orelse = TypeUtils.has_complete_return(stmt.orelse)
				if then and orelse: return True
			elif isinstance(stmt, (ast.For, ast.While)): continue
			elif isinstance(stmt, ast.Try):
				blocks = [stmt.body, stmt.orelse, stmt.finalbody] + [h.body for h in stmt.handlers]
				if all(TypeUtils.has_complete_return(b) for b in blocks if b): return True
			elif isinstance(stmt, ast.With):
				if TypeUtils.has_complete_return(stmt.body): return True
			elif isinstance(stmt, ast.Match):
				if all(TypeUtils.has_complete_return(case.body) for case in stmt.cases): return True
			elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): continue
		return False
