from __future__ import annotations

from typify.logging import logger
from typify.preprocessing.symbol_table import (
	Name, 
	ClassDefinition, 
	FunctionDefinition
)

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
		from typify.inferencing.generic_utils import GenericConstruct
		from typify.inferencing.expression import TypeExpr, PackedExpr

		self.names: dict[str, Name] = {}
		self.store: list[ReferenceSet] = []
		self.type_expr: TypeExpr = None
		self.packed_expr: PackedExpr = None
		self.origin: ClassDefinition | FunctionDefinition = None

		self.genconstruct: dict[ClassDefinition, GenericConstruct] = {}
	
	def instanceof(self, typedef: ClassDefinition):
		from typify.inferencing.commons import Checker
		return Checker.match_origin(self.type_expr.base, typedef)

	def refresh_type_data(self, type_expr):
		from typify.inferencing.generic_utils import GenericUtils
		from typify.inferencing.expression import TypeExpr
		
		self.type_expr: TypeExpr = type_expr

		if self.type_expr.base:
			self.genconstruct = self.type_expr.base.genconstruct.copy()
			for k, v in self.genconstruct.items():
				self.genconstruct[k] = v.copy()
			
			GenericUtils.apply_substitution_to_class_args(
				self.type_expr.base, 
				self.type_expr.typeargs, 
				self.genconstruct
			)
				
	def __repr__(self) -> str:
		return self.label()
	
	def get_name(self, id: str) -> Name:
		name = self.names.get(id)
		if not name:
			name = Name(id)
			self.names[id] = name
		return name
	
	def label(self) -> str:
		return f"instance@{repr(self.type_expr)}"