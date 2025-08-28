from __future__ import annotations
from dataclasses import dataclass

from typify.inferencing.expression import TypeExpr
from typify.preprocessing.instance_utils import Instance
from typify.preprocessing.symbol_table import ClassDefinition

@dataclass
class GenericTree:
	subs: dict[Placeholder, Placeholder | list[Placeholder]]
	gentree: dict[ClassDefinition, GenericTree]

@dataclass
class GenericConstruct:
	subs: dict[Placeholder, Placeholder | list[Placeholder]]
	concsubs: dict[Placeholder, TypeExpr | list[TypeExpr]]

	def copy(self):
		subs_copy = {
			k: v.copy() if isinstance(v, list) else v
			for k, v in self.subs.items()
		}
		concsubs_copy = {
			k: v.copy() if isinstance(v, list) else v
			for k, v in self.concsubs.items()
		}
		return GenericConstruct(subs_copy, concsubs_copy)

@dataclass(frozen=True)
class Placeholder:
	owner: ClassDefinition
	typevar: Instance

	def update_type(
		self,
		concsubs: dict[Placeholder, TypeExpr | list[TypeExpr]],
		incoming: TypeExpr | list[TypeExpr]
	) -> TypeExpr | list[TypeExpr]:
		from typify.inferencing.typeutils import TypeUtils

		old = concsubs.get(self, None)

		if isinstance(old, list):
			result = [
				TypeUtils.unify_from_exprs([old[i], incoming[i]])
				for i in range(len(min(incoming, old, key=len)))
			]
			longer = old if len(old) > len(incoming) else incoming
			result.extend(longer[len(result):])
			return result

		elif isinstance(old, TypeExpr):
			return TypeUtils.unify_from_exprs([old, incoming])
		else:
			return incoming

	def __str__(self):
		ownerid = f"{self.owner.parent.id}." if self.owner else ""
		return f"{ownerid}{self.typevar.instantiator.parent.id}"

	def __repr__(self):
		return str(self)
	
	def __hash__(self):
		return hash((
			getattr(self, "owner", None),
			getattr(self, "typevar", None),
		))
