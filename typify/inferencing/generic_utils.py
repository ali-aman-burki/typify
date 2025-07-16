from __future__ import annotations
from dataclasses import dataclass
from collections import OrderedDict

from typify.inferencing.expression import TypeExpr, PackedExpr
from typify.preprocessing.instance_utils import Instance
from typify.inferencing.commons import Typing
from typify.preprocessing.symbol_table import ClassDefinition

@dataclass
class GenericTree:
	subs: dict[Instance, Instance]
	genmap: dict[ClassDefinition, GenericTree]

class GenericRegistry:

	def __init__(self):
		self.typevars: dict[Instance, TypeExpr] = {}
		self.typevartuples: dict[Instance, list[TypeExpr]] = {}
		
	def update_typevar(self, typevar: Instance, typeexpr: TypeExpr):
		from typify.inferencing.typeutils import TypeUtils
		
		existing_expr = self.typevars.get(typevar)
		if existing_expr:
			self.typevars[typevar] = TypeUtils.unify_from_exprs([existing_expr, typeexpr])
		else:
			self.typevars[typevar] = typeexpr

		return self.typevars[typevar]
	
	def update_typevartuple(self, typevartuple: Instance, typeargs: list[TypeExpr]):
		from typify.inferencing.typeutils import TypeUtils

		existing = self.typevartuples.get(typevartuple, [])
		result = []
		for i in range(max(len(existing), len(typeargs))):
			a = existing[i] if i < len(existing) else None
			b = typeargs[i] if i < len(typeargs) else None

			if a and b: result.append(TypeUtils.unify_from_exprs([a, b]))
			elif a: result.append(a)
			elif b: result.append(b)

		self.typevartuples[typevartuple] = result
		return result
	
global_registry: GenericRegistry = GenericRegistry()

class GenericUtils:

	@staticmethod
	def pretty_print_genmap(tree: dict[ClassDefinition, GenericTree], indent: int = 0):
		def indent_str(level):
			return '  ' * level

		for clsdef, gentree in tree.items():
			if not gentree.subs and not gentree.genmap: continue

			print(f"{indent_str(indent)}Class: {clsdef.parent.id}")
			if gentree.subs:
				print(f"{indent_str(indent + 1)}Subs:")
				for inst_from, inst_to in gentree.subs.items():
					print(f"{indent_str(indent + 2)}{inst_from.tid} -> {inst_to.tid}")

			if gentree.genmap:
				print(f"{indent_str(indent + 1)}GenMap:")
				GenericUtils.pretty_print_genmap(gentree.genmap, indent + 2)

	@staticmethod
	def build_genmap(classdef: ClassDefinition, prev: list[Instance] = None):
		placeholders = GenericUtils.init_placeholders(classdef.genbases)
		subs = {item: item for item in placeholders}
		
		if prev:
			num_placeholders = len(placeholders)
			for i in range(min(len(prev), num_placeholders)):
				subs[placeholders[i]] = prev[i]
		
		result = GenericTree(subs, {})
		
		for base in classdef.genbases:
			if base.packed_expr.base.origin == Typing.get_type("Generic"):
				continue

			base_placeholders = GenericUtils.init_placeholders([base])
			base_subs = []
			for bp in base_placeholders:
				if bp in subs: base_subs.append(subs[bp])
				else: base_subs.append(bp)
			
			base_classdef = base.packed_expr.base.origin
			result.genmap[base_classdef] = GenericUtils.build_genmap(base_classdef, base_subs)
		
		return result

	@staticmethod
	def collect_placeholders(packed_expr: PackedExpr) -> list[Instance]:
		result = []
		if packed_expr.base.origin in (Typing.get_type("TypeVar"), Typing.get_type("TypeVarTuple")):
			result.append(packed_expr.base)
		
		for arg in packed_expr.args:
			result += GenericUtils.collect_placeholders(arg)
		
		return result
	
	@staticmethod
	def init_placeholders(generic_bases: list[Instance]):
		for base in generic_bases:
			if base.packed_expr.base.origin == Typing.get_type("Generic"):
				return GenericUtils.collect_placeholders(base.packed_expr)

		g_placeholders = []
		for base in generic_bases:
			placeholders = GenericUtils.collect_placeholders(base.packed_expr)
			g_placeholders.extend(placeholders)

		return list(OrderedDict.fromkeys(g_placeholders))

	@staticmethod
	def update_registry(
		registry: GenericRegistry, 
		typeargs: list[TypeExpr]
	) -> None:
		from typify.inferencing.typeutils import TypeUtils

		typevars = registry.typevars
		existing_keys = list(typevars.keys())
		
		for i in range(len(typeargs)):
			key = TypeUtils.get_safe(
				existing_keys, 
				i, 
				TypeUtils.instantiate(Typing.get_type("TypeVar"))
			)
			typevars[key] = typeargs[i]