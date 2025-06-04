from src.annotation_types import *
from src.builtins_ctn import builtins
from src.symbol_table import Table

class TypeUtils:

	@staticmethod
	def count_unresolved_types(t) -> int:
		if isinstance(t, UnresolvedType):
			return 1
		elif isinstance(t, UnionType):
			return sum(TypeUtils.count_unresolved_types(sub) for sub in t.types)
		elif isinstance(t, OptionalType):
			return TypeUtils.count_unresolved_types(t.element_type)
		elif isinstance(t, (ListType, SetType)):
			return TypeUtils.count_unresolved_types(t.element_type)
		elif isinstance(t, DictType):
			return TypeUtils.count_unresolved_types(t.key_type) + TypeUtils.count_unresolved_types(t.value_type)
		elif isinstance(t, TupleType):
			return sum(TypeUtils.count_unresolved_types(el) for el in t.element_types)
		else:
			return 0

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


	@staticmethod
	def unwrap(unified_type: TypeAnnotation) -> list[Type]:
		if isinstance(unified_type, UnionType):
			return unified_type.types
		elif isinstance(unified_type, OptionalType):
			if isinstance(unified_type.element_type, UnionType):
				return unified_type.element_type.types + [Type(builtins.classes["NoneType"])]
			else:
				return [unified_type.element_type, Type(builtins.classes["NoneType"])]
		else:
			return [unified_type]
	
	@staticmethod
	def instantiate(unified_type: TypeAnnotation) -> list[Table]:
		unwrapped = TypeUtils.unwrap(unified_type)
		points_to = [t.type_def.get_type_class().create_instance(t.type_def) for t in unwrapped if not isinstance(t, UnresolvedType)]
		return points_to

	@staticmethod
	def select_more_resolved_type(
		annotated_bundle: tuple[TypeAnnotation, list[Table]],
		inferred_bundle: tuple[TypeAnnotation, list[Table]]
	) -> tuple[TypeAnnotation, list[Table]]:
		annotated_type, _ = annotated_bundle
		inferred_type, _ = inferred_bundle

		a_u_count = TypeUtils.count_unresolved_types(annotated_type)
		i_u_count = TypeUtils.count_unresolved_types(inferred_type)

		if i_u_count < a_u_count: return inferred_bundle
		elif a_u_count < i_u_count: return annotated_bundle
		elif a_u_count == i_u_count == 0: return inferred_bundle
		else: return annotated_bundle