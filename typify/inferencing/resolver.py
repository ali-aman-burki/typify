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
	Builtins
)

@dataclass
class NamePack:
	groups: list[set[tuple[NameTable, DefinitionTable]] | NamePack]

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

	def resolve_target(self, expr: ast.expr) -> NamePack:
		position = (expr.lineno, expr.col_offset)
		defkey = (self.context.module_meta.table, position)

		if isinstance(expr, ast.Name):
			nametable = self.symbol.merge_name(NameTable(expr.id))
			self.namespace.override_name(nametable)
			return NamePack([{(nametable, DefinitionTable(defkey))}])

		elif isinstance(expr, (ast.Tuple, ast.List)):
			pack = NamePack([])
			for elt in expr.elts:
				pack.groups += self.resolve_target(elt).groups
			return pack

		elif isinstance(expr, ast.Attribute):
			instances = self.resolve_value(expr.value)
			pack = NamePack([])
			group = set()
			for instance in instances:
				if expr.attr in instance.names:
					group.add((instance.names[expr.attr], DefinitionTable(defkey)))
				else:
					newname = NameTable(expr.attr)
					if instance.origin: newname = instance.origin.set_name(newname)
					instance.override_name(newname)
					group.add((newname, DefinitionTable(defkey)))
			pack.groups.append(group)
			return pack

		return NamePack([])
			
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
			instance = TypeUtils.instantiate(typeclass)
			for elt in node.elts:
				group = self.resolve_target(elt)
				instance.store.append(group)
			return {instance}
		
		elif isinstance(node, ast.Set):
			typeclass = Builtins.get_type("set")
			instance = TypeUtils.instantiate(typeclass)
			return {instance}
		
		elif isinstance(node, ast.Tuple):
			typeclass = Builtins.get_type("tuple")
			instance = TypeUtils.instantiate(typeclass)
			for elt in node.elts:
				group = self.resolve_target(elt)
				instance.store.append(group)
			return {instance}
		
		elif isinstance(node, ast.Dict):
			typeclass = Builtins.get_type("dict")
			instance = TypeUtils.instantiate(typeclass)
			return {instance}
		
		elif isinstance(node, ast.Name):
			name = self.lookup_name(node.id)
			namedef = name.get_latest_definition()
			return namedef.points_to if namedef else set()
		
		elif isinstance(node, ast.Attribute):
			value_points_tos = self.resolve_value(node.value)
			results = set()
			for pt in value_points_tos:
				if node.attr in pt.names:
					namedef = pt.names[node.attr].get_latest_definition()
					results.update(namedef.points_to)
			return results
		else:
			return set()
	
	def process_assignment(
			self, 
			resolved_target: NamePack, 
			resolved_value: set[InstanceTable]
		):
		
		for group in resolved_target.groups:
			if isinstance(group, NamePack):
				self.process_assignment(group, resolved_value)
			else:
				for item in group:
					nametable = item[0]
					namedef = nametable.add_definition(item[1])
					namedef.points_to.update(resolved_value)