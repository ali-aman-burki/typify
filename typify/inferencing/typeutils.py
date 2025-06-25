from __future__ import annotations
import ast

from typify.preprocessing.symbol_table import (
    InstanceTable, 
    DefinitionTable
)
from types import EllipsisType

class TypeExpr:
	def __init__(
			self, 
			type_def: DefinitionTable, 
			args: list[TypeExpr | list[TypeExpr] | ast.Constant | EllipsisType] | None = None
		):
		self.type_def = type_def
		self.args = args if args else []
	
	def __repr__(self):
		if not self.type_def: return "$unresolved$"
		fqn = self.type_def.parent.fqn
		joined = ", ".join(
			(
				f"[{', '.join(repr(a) for a in arg)}]" if isinstance(arg, list)
				else repr(arg.value) if isinstance(arg, ast.Constant)
				else "..." if isinstance(arg, EllipsisType)
				else repr(arg)
			)
			for arg in self.args
		)
		trailing = f"[{joined}]" if joined else ""
		return f"{fqn}{trailing}"

class TypeUtils:

	@staticmethod
	def instantiate(
		type_def: DefinitionTable, 
		args: list[TypeExpr | list[TypeExpr] | EllipsisType] | None = None
		) -> InstanceTable:

		instance = InstanceTable()
		TypeUtils.update_type_expr(instance, TypeExpr(type_def, args if args else []))
		return instance
	
	@staticmethod
	def update_type_expr(
		instance: InstanceTable, 
		type_expr: TypeExpr
		):
		
		instance.type_expr = type_expr
		fqn = type_expr.type_def.parent.fqn if type_expr.type_def else "$unresolved$"
		instance.key = f"instance@{fqn}"
