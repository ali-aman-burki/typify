from __future__ import annotations
from dataclasses import dataclass
from collections import OrderedDict
from collections import deque

from typify.inferencing.expression import TypeExpr, PackedExpr
from typify.preprocessing.instance_utils import Instance
from typify.preprocessing.symbol_table import ClassDefinition
from typify.inferencing.commons import Typing, Checker

@dataclass
class GenericTree:
    subs: dict[Placeholder, Placeholder | list[Placeholder]]
    gentree: dict[ClassDefinition, GenericTree]

@dataclass
class GenericConstruct:
	subs: dict[Placeholder, Placeholder | list[Placeholder]]
	concsubs: dict[Placeholder, TypeExpr | list[TypeExpr]]

	def copy(self):
		subs_copy = self.subs.copy()
		for k, v in subs_copy.items():
			if isinstance(v, list): 
				subs_copy[k] = v.copy()
		
		concsubs_copy = self.concsubs.copy()
		for k, v in concsubs_copy.items():
			if isinstance(v, list): 
				concsubs_copy[k] = v.copy()
		
		return GenericConstruct(subs_copy, concsubs_copy)

@dataclass(frozen=True)
class Placeholder:
    owner_class: ClassDefinition
    typevar: Instance

    def __str__(self):
        return f"{self.owner_class.parent.id}.{self.typevar.type_expr.base.parent.id}"

    def __repr__(self):
        return str(self)

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
			classdef = ph.owner_class
			if classdef in flattened:
				flattened[classdef].concsubs[ph] = value

	@staticmethod
	def pretty_print_gentree(
		tree: dict[ClassDefinition, GenericTree], 
		indent: int = 0
	):
		
		def indent_str(level):
			return "  " * level

		for clsdef, gentree in tree.items():
			if not gentree.subs and not gentree.gentree:
				continue

			print(f"{indent_str(indent)}Class: {clsdef.parent.id}")

			if gentree.subs:
				print(f"{indent_str(indent + 1)}Subs:")
				for inst_from, inst_to in gentree.subs.items():
					if isinstance(inst_to, list):
						targets = ", ".join(repr(t) for t in inst_to)
						print(f"{indent_str(indent + 2)}{repr(inst_from)} -> [{targets}]")
					else:
						print(f"{indent_str(indent + 2)}{repr(inst_from)} -> {repr(inst_to)}")

			if gentree.gentree:
				print(f"{indent_str(indent + 1)}gentree:")
				GenericUtils.pretty_print_gentree(gentree.gentree, indent + 2)
	
	@staticmethod
	def pretty_print_genconstruct(
		flat: dict[ClassDefinition, GenericConstruct], 
		indent: int = 0
	):
		
		def indent_str(level: int) -> str:
			return "  " * level

		for clsdef, construct in flat.items():
			if not construct.subs and not construct.concsubs:
				continue

			print(f"{indent_str(indent)}Class: {clsdef.parent.id}")
			
			if construct.subs:
				print(f"{indent_str(indent + 1)}Subs:")
				for k, v in construct.subs.items():
					if isinstance(v, list):
						vals = ", ".join(repr(x) for x in v)
						print(f"{indent_str(indent + 2)}{repr(k)} -> [{vals}]")
					else:
						print(f"{indent_str(indent + 2)}{repr(k)} -> {repr(v)}")

			if construct.concsubs:
				print(f"{indent_str(indent + 1)}Concrete Subs:")
				for k, v in construct.concsubs.items():
					if isinstance(v, list):
						vals = ", ".join(str(x) if x is not None else "None" for x in v)
						print(f"{indent_str(indent + 2)}{repr(k)} -> [{vals}]")
					else:
						val_str = str(v) if v is not None else "None"
						print(f"{indent_str(indent + 2)}{repr(k)} -> {val_str}")

	@staticmethod
	def flatten_gentree(gentree: dict[ClassDefinition, GenericTree]) -> dict[ClassDefinition, GenericConstruct]:
		flat: dict[ClassDefinition, GenericConstruct] = {}

		for clsdef, gentree in gentree.items():
			flat[clsdef] = GenericConstruct(
				subs=gentree.subs,
				concsubs={ph: None for ph in gentree.subs}
			)

			nested = GenericUtils.flatten_gentree(gentree.gentree)
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
		if packed_expr.base.type_expr.base in (
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