from __future__ import annotations
import ast

from typify.inferencing.commons import Typing
from typify.preprocessing.precollector import PreCollector
from typify.preprocessing.instance_utils import (
	ReferenceSet,
	Instance
)
from typify.preprocessing.symbol_table import (
	ClassDefinition
)

class TypeVarRegistry:

	def __init__(self):
		self.typevars: dict[Instance, TypeExpr] = {}
		
	def update(self, typevar: Instance, typeexpr: TypeExpr):
		existing = [self.typevars[typevar]] if typevar in self.typevars else []
		self.typevars[typevar] = TypeUtils.unify_from_exprs(existing + [typeexpr])
		return self.typevars[typevar]
	
	def get(self, typevar: Instance):
		return self.typevars.get(typevar)

global_registry: TypeVarRegistry = TypeVarRegistry()

class TypeExpr:

	@staticmethod
	def from_ast(node: ast.Expr) -> TypeExpr:

		return None

	def __init__(
			self, 
			base: ClassDefinition, 
			typeargs: list[TypeExpr] = None
		):
		self.base = base
		self.typeargs = typeargs or []

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
		
class TypeUtils:

	@staticmethod
	def type_expr_from_refset(refset: ReferenceSet):
		type_exprs = []
		for ref in refset:
			type_exprs.append(ref.type_expr)
		return TypeUtils.unify_from_exprs(type_exprs)

	@staticmethod
	def instantiate_from_type_expr(unified_type_expr: TypeExpr) -> ReferenceSet:
		result = ReferenceSet()
		if unified_type_expr.base == Typing.get_type("Union"):
			for typeexpr in unified_type_expr.typeargs:
				result.add(TypeUtils.instantiate(typeexpr.base, typeexpr.typeargs))
		else:
			result.add(TypeUtils.instantiate(unified_type_expr.base, unified_type_expr.typeargs))
		return result

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
		return TypeUtils.unify_from_exprs([ref.type_expr for ref in refset])

	@staticmethod
	def instantiate(
		typedef: ClassDefinition, 
		typeargs: list[Instance] | None = None
		) -> Instance:

		instance = Instance()
		instance.type_expr = TypeExpr(typedef, typeargs)
		TypeUtils.update_registry(instance.registry, instance.type_expr.typeargs)
		return instance

	@staticmethod
	def update_registry(
		registry: TypeVarRegistry, 
		typeargs: list[TypeExpr]
	) -> None:
		typevars = registry.typevars
		existing_keys = list(typevars.keys())
		
		for i in range(len(typeargs)):
			key = TypeUtils.get_safe(
				existing_keys, 
				i, 
				TypeUtils.instantiate(Typing.get_type("TypeVar"))
			)
			typevars[key] = typeargs[i]

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
