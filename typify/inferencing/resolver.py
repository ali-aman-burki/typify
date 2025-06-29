from __future__ import annotations
from dataclasses import dataclass

import ast

from typify.inferencing.typeutils import TypeUtils
from typify.preprocessing.symbol_table import (
	Table,
	NameTable,
	PackageTable,
	LibraryTable,
	InstanceTable,
	DefinitionTable,
)
from typify.inferencing.commons import (
	Context,
	Builtins,
	Typing
)

@dataclass(frozen=True)
class TargetEntry:
    name: NameTable
    definition: DefinitionTable

@dataclass
class PackGroup:
	groups: list[set[TargetEntry] | PackGroup]
	starred: bool

class Resolver:
	def __init__(
			self, 
			context: Context, 
			symbol: Table, 
			namespace: InstanceTable
		):
		self.context = context
		self.symbol = symbol
		self.namespace = namespace

	def lookup_name(self, name: str) -> NameTable:
		current_symbol = self.symbol
		
		while not isinstance(current_symbol, (LibraryTable, PackageTable)):
			if name in current_symbol.names: 
				return current_symbol.names[name]
			else:
				current_symbol = current_symbol.get_enclosing_table()
		
		if name in Builtins.module().names:
			return Builtins.module().names[name]
		
		return None

	def resolve_target(self, expr: ast.expr) -> PackGroup:
		position = (expr.lineno, expr.col_offset)
		defkey = (self.context.module_meta.table, position)

		if isinstance(expr, ast.Name):
			nametable = self.symbol.merge_name(NameTable(expr.id))
			self.namespace.override_name(nametable)
			entry = TargetEntry(nametable, DefinitionTable(defkey))
			return PackGroup(groups=[{entry}], starred=False)

		elif isinstance(expr, (ast.Tuple, ast.List)):
			inner_groups: list[set[TargetEntry] | PackGroup] = []
			for elt in expr.elts:
				subgroup = self.resolve_target(elt)
				inner_groups.append(subgroup)
			return PackGroup(groups=inner_groups, starred=False)

		elif isinstance(expr, ast.Starred):
			resolved = self.resolve_target(expr.value)
			return PackGroup(groups=resolved.groups, starred=True)

		elif isinstance(expr, ast.Attribute):
			instances = self.resolve_value(expr.value)
			group: set[TargetEntry] = set()
			for instance in instances:
				if expr.attr in instance.names:
					group.add(TargetEntry(instance.names[expr.attr], DefinitionTable(defkey)))
				else:
					newname = NameTable(expr.attr)
					if instance.origin:
						newname = instance.origin.set_name(newname)
					instance.override_name(newname)
					group.add(TargetEntry(newname, DefinitionTable(defkey)))
			return PackGroup(groups=[group], starred=False)
		else:
			return PackGroup(groups=[], starred=False)

			
	def resolve_value(self, node: ast.Expr) -> set[InstanceTable]:
		if isinstance(node, ast.Constant):
			typeclass = Builtins.get_type(type(node.value).__name__)
			instance = TypeUtils.instantiate(typeclass)
			return {instance}
		
		elif isinstance(node, ast.JoinedStr):
			typeclass = Builtins.get_type("str")
			instance = TypeUtils.instantiate(typeclass)
			return {instance}
		
		elif isinstance(node, ast.List):
			typeclass = Builtins.get_type("list")
			typeargs = []
			for elt in node.elts:
				resolved = self.resolve_value(elt)
				unified = TypeUtils.unify([r.type_expr for r in resolved])
				typeargs.append(unified)
			instance = TypeUtils.instantiate(typeclass, [TypeUtils.unify(typeargs)])
			return {instance}
		
		elif isinstance(node, ast.Set):
			typeclass = Builtins.get_type("set")
			typeargs = []
			for elt in node.elts:
				resolved = self.resolve_value(elt)
				unified = TypeUtils.unify([r.type_expr for r in resolved])
				typeargs.append(unified)
			instance = TypeUtils.instantiate(typeclass, [TypeUtils.unify(typeargs)])
			return {instance}
		
		elif isinstance(node, ast.Tuple):
			typeclass = Builtins.get_type("tuple")
			store = []
			typeargs = []
			for elt in node.elts:
				resolved = self.resolve_value(elt)
				unified = TypeUtils.unify([r.type_expr for r in resolved])
				typeargs.append(unified)
				store.append(resolved)
			instance = TypeUtils.instantiate(typeclass, typeargs)
			instance.store = store
			return {instance}
		
		elif isinstance(node, ast.Dict):
			typeclass = Builtins.get_type("dict")
			instance = TypeUtils.instantiate(typeclass)
			return {instance}
		
		elif isinstance(node, ast.Name):
			name = self.lookup_name(node.id)
			if name: return name.get_latest_definition().points_to
			return {TypeUtils.instantiate(Typing.get_type("Any"))}
		
		elif isinstance(node, ast.Attribute):
			value_points_tos = self.resolve_value(node.value)
			results = set()
			for pt in value_points_tos:
				if node.attr in pt.names:
					namedef = pt.names[node.attr].get_latest_definition()
					results.update(namedef.points_to)
			return results
		else:
			return {TypeUtils.instantiate(Typing.get_type("Any"))}
	
	def process_assignment(
			self, 
			resolved_target: PackGroup, 
			resolved_value: set[InstanceTable]
		):
		for group in resolved_target.groups:
			if isinstance(group, PackGroup):
				self.process_assignment(group, resolved_value)
			else:
				for item in group:
					nametable = item.name
					namedef = nametable.add_definition(item.definition)
					namedef.points_to.update(resolved_value)
	
	def pretty_print_packgroup(self, pg: PackGroup, indent: int = 0):
		indent_str = "  " * indent
		star = "Starred " if pg.starred else ""
		print(f"{indent_str}{star}PackGroup:")
		for group in pg.groups:
			if isinstance(group, PackGroup):
				self.pretty_print_packgroup(group, indent + 1)
			else:
				print(f"{indent_str}  Group:")
				for entry in group:
					print(f"{indent_str}    - {entry.name.key} (line {entry.definition.position[0]})")
