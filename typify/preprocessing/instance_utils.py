from __future__ import annotations

import ast

from typify.logging import logger
from typify.preprocessing.symbol_table import (
	Name, 
	ClassDefinition, 
	FunctionDefinition
)

class ReferenceSet:
	def __init__(self, *reference_list: Instance):
		self.references = dict.fromkeys(reference_list)

	def __repr__(self) -> str: return repr(self.as_type())
	def __len__(self) -> int: return len(self.references)
	def __contains__(self, item: Instance) -> bool: return item in self.references
	def __iter__(self): return iter(self.references)

	def copy(self):
		c = ReferenceSet()
		c.references = self.references.copy()
		return c

	def add(self, reference: Instance):
		self.references[reference] = None

	def update(self, other: 'ReferenceSet'):
		for ref in other:
			self.references[ref] = None
	
	def ref(self) -> Instance | None:
		if len(self.references) > 1: 
			logger.error("Multiple references found where 1 was expected.")
		if not self.references:
			return None
		return next(reversed(self.references))
	
	def as_type(self):
		from typify.inferencing.typeutils import TypeUtils
		return TypeUtils.unify_from_exprs([ref.as_type() for ref in self.references])

class Instance:
	def __init__(self, instantiator: ClassDefinition):
		from typify.inferencing.generics.model import GenericConstruct
		from typify.inferencing.expression import PackedExpr
		from typify.inferencing.commons import ParameterEntry

		self.instantiator: ClassDefinition = instantiator
		self.names: dict[str, Name] = {}
		self.store: list[ReferenceSet] = []
		self.packed_expr: PackedExpr = None
		self.origin: ClassDefinition | FunctionDefinition = None
		self.cval = None
		
		self.tree: ast.FunctionDef | ast.AsyncFunctionDef = None
		self.parameters: dict[str, ParameterEntry] = {}
		self.return_annotation: Instance = None

		self.genconstruct: dict[ClassDefinition, GenericConstruct] = {}
	
	def instanceof(self, *typedefs: ClassDefinition | tuple[ClassDefinition, ...]) -> bool:
		from typify.inferencing.commons import Checker

		if len(typedefs) == 1 and isinstance(typedefs[0], tuple):
			typedefs = typedefs[0]

		return any(Checker.match_origin(self.instantiator, td) for td in typedefs)

	def attribute_lookup(
			self, 
			attr: str
		) -> Name:
		
		from typify.inferencing.commons import Checker

		if attr in self.names: return self.names[attr]
		
		if Checker.is_type(self):
			for m in self.origin.mro:
				if attr in m.names: return m.names[attr]
		else:
			for m in self.instantiator.mro:
				if attr in m.names: return m.names[attr]
		
		return None

	def update_type_info(
			self, 
			instantiator: ClassDefinition, 
			typeargs: list = None
		):
		from typify.inferencing.generics.utils import GenericUtils
		from typify.inferencing.expression import TypeExpr
		
		typeargs: list[TypeExpr] = typeargs if typeargs else []
		self.instantiator = instantiator

		if self.instantiator:
			self.genconstruct = self.instantiator.genconstruct.copy()
			for k, v in self.genconstruct.items():
				self.genconstruct[k] = v.copy()
			
			GenericUtils.apply_substitution_to_class_args(
				self.instantiator, 
				typeargs, 
				self.genconstruct
			)

	def as_type(self):
		from typify.inferencing.expression import TypeExpr
		from typify.inferencing.commons import Typing, Checker

		base = self.instantiator
		args = []

		if self.genconstruct.keys():
			gencons = self.genconstruct[base]
			for k, v in gencons.concsubs.items():
				if Checker.is_typevartuple(k.typevar):
					args.extend(v if v else [])
				else:
					args.append(v if v else TypeExpr(Typing.get_type("Any")))
			
		return TypeExpr(base, args)

	def __repr__(self) -> str:
		return self.label()
	
	def get_name(self, id: str) -> Name:
		name = self.names.get(id)
		if not name:
			name = Name(id)
			self.names[id] = name
		return name
	
	def label(self) -> str:
		return f"instance@{repr(self.as_type())}"