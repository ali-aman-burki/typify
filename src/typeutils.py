from src.symbol_table import Table, InstanceTable
from types import EllipsisType

import ast

class TypeExpr:
	def __init__(self, base: Table, args: "list[TypeExpr | list[TypeExpr] | ast.Constant | EllipsisType]"):
		self.base = base
		self.args = args
	
	def __repr__(self):
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
	def create_instance(template: Table, args: list[TypeExpr | list[TypeExpr] | EllipsisType]) -> InstanceTable:
		fqn = template.get_type_class().fqn
		instance = InstanceTable(f"instance@{fqn}")
		instance.type = TypeExpr(template, args)
		return instance
