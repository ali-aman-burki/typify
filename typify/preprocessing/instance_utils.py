from __future__ import annotations

from typify.logging import logger

class ReferenceSet:

	def __init__(self, *reference_list: Instance):
		self.references = set(reference_list)
	
	def __repr__(self) -> str: return repr(self.as_type())
	def __len__(self) -> int: return len(self.references)
	def __contains__(self, item: Instance) -> bool: return item in self.references
	def __iter__(self): return iter(self.references)
	
	def copy(self):
		c = ReferenceSet()
		c.update(self)
		return c

	def add(self, reference: Instance):
		self.references.add(reference)
	
	def update(self, other: ReferenceSet):
		self.references.update(other.references)
	
	def ref(self) -> Instance | None:
		if len(self.references) != 1: 
			logger.error("Multiple references found where 1 was expected.")
		return next(iter(self.references))
	
	def as_type(self):
		from typify.inferencing.typeutils import TypeUtils
		return TypeUtils.unify(self)

class Instance:
	def __init__(self):
		from typify.inferencing.typeutils import TypeExpr
		from typify.preprocessing.newsymbols import (
			Name, 
			ClassDefinition, 
			FunctionDefinition
		)

		self.attributes: dict[str, Name] = {}
		self.store: list[ReferenceSet] = []
		self.type_expr: TypeExpr = None
		self.origin: ClassDefinition | FunctionDefinition = None
	
	def __repr__(self) -> str:
		return self.label()

	def label(self) -> str:
		return f"instance@{repr(self.type_expr)}"