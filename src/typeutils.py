from src.contanier_types import *
from src.builtins_ctn import builtins

class TypeUtils:

	@staticmethod
	def unify(types, allow_optional: bool = False):
		seen = []

		def add_unique(t):
			if isinstance(t, UnionType):
				for subtype in t.types:
					if subtype not in seen:
						seen.append(subtype)
			elif t not in seen:
				seen.append(t)

		for t in types:
			add_unique(t)

		none_type = Type(builtins.classes["NoneType"])
		has_none = none_type in seen

		if has_none:
			non_none_types = [t for t in seen if t != none_type]
			if non_none_types:
				unified_non_none = TypeUtils.unify(non_none_types, allow_optional=allow_optional)
				if allow_optional:
					return OptionalType(unified_non_none)
				else:
					return unified_non_none
			else:
				return none_type if allow_optional else AnyType()

		if len(seen) > 1:
			return UnionType(seen)
		elif seen:
			return seen[0]
		else:
			return AnyType()

