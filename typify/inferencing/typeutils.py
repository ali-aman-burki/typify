from typify.preprocessing.symbol_table import Table, InstanceTable
from types import EllipsisType

import ast

class TypeExpr:
	def __init__(self, base: Table, args: "list[TypeExpr | list[TypeExpr] | ast.Constant | EllipsisType]"):
		self.base = base
		self.args = args
	
	def __repr__(self):
		if not self.base: return "$unresolved$"
		fqn = self.base.get_type_class().fqn
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
	def instantiate(template: Table, args: list[TypeExpr | list[TypeExpr] | EllipsisType]) -> InstanceTable:
		fqn = template.get_type_class().fqn if template else "$unresolved$"
		instance = InstanceTable(f"instance@{fqn}")
		instance.type = TypeExpr(template, args)
		return instance
