from collections import deque, OrderedDict

from typify.preprocessing.symbol_table import ClassDefinition
from typify.preprocessing.instance_utils import Instance
from typify.inferencing.commons import Typing, Checker

from typify.inferencing.expression import (
    TypeExpr, 
    PackedExpr
)
from typify.inferencing.generics.model import (
    Placeholder, 
    GenericTree, 
    GenericConstruct
)

class GenericUtils:

	@staticmethod
	def apply_substitution_to_class_args(
		classdef: ClassDefinition,
		concrete_args: list[TypeExpr],
		flattened: dict[ClassDefinition, GenericConstruct]
	):
		placeholders = list(flattened[classdef].subs.keys())
		binding = GenericUtils.match_type_exprs(placeholders, concrete_args)

		for placeholder, concrete in binding.items():
			GenericUtils.apply_substitution(placeholder, concrete, flattened)

	@staticmethod
	def apply_substitution(
		source: Placeholder,
		value: TypeExpr | list[TypeExpr],
		flattened: dict[ClassDefinition, GenericConstruct]
	):
		alias_graph: dict[Placeholder, set[Placeholder]] = {}

		for classdef, construct in flattened.items():
			for key, val in construct.subs.items():
				if isinstance(val, list):
					for v in val:
						alias_graph.setdefault(v, set()).add(key)
						alias_graph.setdefault(key, set()).add(v)
				else:
					alias_graph.setdefault(val, set()).add(key)
					alias_graph.setdefault(key, set()).add(val)

		queue = deque([source])
		visited = set([source])

		while queue:
			current = queue.popleft()
			for neighbor in alias_graph.get(current, []):
				if neighbor not in visited:
					visited.add(neighbor)
					queue.append(neighbor)

		for ph in visited:
			classdef = ph.owner
			if classdef in flattened:
				flattened[classdef].concsubs[ph] = ph.update_type(flattened[classdef].concsubs, value)

	@staticmethod
	def flatten_gentree(gentree: dict[ClassDefinition, GenericTree]) -> dict[ClassDefinition, GenericConstruct]:
		flat: dict[ClassDefinition, GenericConstruct] = {}

		for clsdef, ingentree in gentree.items():
			flat[clsdef] = GenericConstruct(
				subs=ingentree.subs,
				concsubs={ph: None for ph in ingentree.subs}
			)

			nested = GenericUtils.flatten_gentree(ingentree.gentree)
			flat.update(nested)

		return flat

	@staticmethod
	def match_type_exprs(
		placeholders: list[Placeholder],
		actual_args: list[TypeExpr]
	) -> dict[Placeholder, TypeExpr | list[TypeExpr]]:
		
		result = {}
		i = 0
		tvts = [p for p in placeholders if p.typevar.instanceof(Typing.get_type("TypeVarTuple"))]

		if len(tvts) > 1:
			raise Exception("Multiple TypeVarTuples not supported.")

		for j, ph in enumerate(placeholders):
			if ph.typevar.instanceof(Typing.get_type("TypeVarTuple")):
				fixed_after = len(placeholders) - (j + 1)
				tvt_len = len(actual_args) - i - fixed_after
				if tvt_len < 0:
					result[ph] = None
					continue

				sliced = actual_args[i:i + tvt_len]
				result[ph] = sliced
				i += tvt_len
			else:
				if i < len(actual_args):
					result[ph] = actual_args[i]
				else:
					result[ph] = None
				i += 1

		return result

	@staticmethod
	def match_placeholders(
		placeholders: list[Placeholder],
		actual_args: list[Placeholder]
	) -> dict[Placeholder, Placeholder | list[Placeholder]]:
		
		result = {}
		i = 0
		tvts = [p for p in placeholders if p.typevar.instanceof(Typing.get_type("TypeVarTuple"))]
		
		if len(tvts) > 1:
			raise Exception("Multiple TypeVarTuples not supported.")

		for j, ph in enumerate(placeholders):
			if ph.typevar.instanceof(Typing.get_type("TypeVarTuple")):
				fixed_after = len(placeholders) - (j + 1)
				tvt_len = len(actual_args) - i - fixed_after
				if tvt_len < 0:
					result[ph] = ph
					continue

				sliced = actual_args[i:i + tvt_len]

				if len(sliced) == 1 and sliced[0].typevar.instanceof(Typing.get_type("TypeVarTuple")):
					result[ph] = sliced[0]
				else:
					result[ph] = sliced

				i += tvt_len
			else:
				if i < len(actual_args):
					result[ph] = actual_args[i]
				else:
					result[ph] = ph
				i += 1

		return result

	@staticmethod
	def build_gentree(
		classdef: ClassDefinition,
		prev: list[Placeholder] = None,
		visited: set[ClassDefinition] = None,
	) -> GenericTree:
		
		if visited is None: visited = set()
		if classdef in visited: return GenericTree({}, {})

		visited.add(classdef)

		placeholders = GenericUtils.init_placeholders(classdef, classdef.genbases)

		if prev is None: subs = {ph: ph for ph in placeholders}
		else: subs = GenericUtils.match_placeholders(placeholders, prev)

		result = GenericTree(subs, {})

		for base in classdef.genbases:
			if Checker.match_origin(base.packed_expr.base.origin, Typing.get_type("Generic")):
				continue

			base_classdef = base.packed_expr.base.origin
			base_placeholders = GenericUtils.init_placeholders(classdef, [base])

			base_args = []
			for bp in base_placeholders:
				mapped = subs.get(bp, bp)
				if isinstance(mapped, list): base_args.extend(mapped)
				else: base_args.append(mapped)

			result.gentree[base_classdef] = GenericUtils.build_gentree(base_classdef, base_args, visited)

		return result

	@staticmethod
	def collect_typevars(packed_expr: PackedExpr) -> list[Instance]:
		result = []
		if packed_expr.base.instanceof(
			Typing.get_type("TypeVar"), 
			Typing.get_type("TypeVarTuple")
		):
			result.append(packed_expr.base)
		
		for arg in packed_expr.args:
			result += GenericUtils.collect_typevars(arg)
		
		return result
	
	@staticmethod
	def init_placeholders(
		owner: ClassDefinition, 
		generic_bases: list[Instance]
	) -> list[Placeholder]:

		for base in generic_bases:
			if Checker.match_origin(base.packed_expr.base.origin, Typing.get_type("Generic")):
				placeholders = GenericUtils.collect_typevars(base.packed_expr)
				return [Placeholder(owner, ph) for ph in placeholders]

		g_placeholders = []
		for base in generic_bases:
			placeholders = GenericUtils.collect_typevars(base.packed_expr)
			g_placeholders.extend([Placeholder(owner, ph) for ph in placeholders])

		unique = list(OrderedDict.fromkeys(g_placeholders))
		return unique