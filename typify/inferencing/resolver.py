from typify.inferencing.typeutils import TypeUtils
from typify.preprocessing.symbol_table import (
    Table,
	NameTable,
	PackageTable,
	LibraryTable,
    InstanceTable,
	DefinitionTable,
	ModuleTable
)
from typify.inferencing.commons import (
    Context,
    Builtins
)

import ast

class Resolver:
	def __init__(self, context: Context, symbol: Table, namespace: InstanceTable):
		self.context = context
		self.symbol = symbol
		self.namespace = namespace

	def create_name(
			self,
			name: str,
			defkey: tuple[ModuleTable, tuple[int, int]],
			namespace: InstanceTable,
			symbol: Table = None,
		):
		nametable = NameTable(name)
		namedef = nametable.add_definition(DefinitionTable(defkey))
		namespace.merge_name(nametable)
		if symbol: symbol.merge_name(nametable)
		return namedef

	def resolve_target(self, expr: ast.expr, namedefs: set[DefinitionTable] = None) -> set[DefinitionTable]:
		if namedefs is None: namedefs = set()
		
		position = (expr.lineno, expr.col_offset)
		defkey = (self.context.module_meta.table, position)

		if isinstance(expr, ast.Name):
			namedefs.add(self.create_name(expr.id, defkey, self.namespace, self.symbol))

		elif isinstance(expr, (ast.Tuple, ast.List)):
			for elt in expr.elts: self.resolve_target(elt, namedefs)
		
		elif isinstance(expr, ast.Attribute):
			results = self.resolve_target(expr.value)
			for namedef in results:
				for pt in namedef.points_to:
					if expr.attr in pt.names: 
						namedefs.add(pt.names[expr.attr].get_latest_definition())
					else:
						namedefs.add(self.create_name(expr.attr, defkey, pt))

		return namedefs

	def lookup_name_def(self, name: str) -> DefinitionTable:
		current_symbol = self.symbol
		
		while not isinstance(current_symbol, (LibraryTable, PackageTable)):
			if name in current_symbol.names: 
				return current_symbol.names[name].get_latest_definition()
			else:
				current_symbol = current_symbol.get_enclosing_table()
		
		if name in Builtins.module().names:
			return Builtins.module().names[name].get_latest_definition()
		
		return None
			
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
			return {instance}
		
		elif isinstance(node, ast.Set):
			typeclass = Builtins.get_type("set")
			instance = TypeUtils.instantiate(typeclass)
			return {instance}
		
		elif isinstance(node, ast.Tuple):
			typeclass = Builtins.get_type("tuple")
			instance = TypeUtils.instantiate(typeclass)
			return {instance}
		
		elif isinstance(node, ast.Dict):
			typeclass = Builtins.get_type("tuple")
			instance = TypeUtils.instantiate(typeclass)
			return {instance}
		elif isinstance(node, ast.Name):
			namedef = self.lookup_name_def(node.id)
			return namedef.points_to
		else:
			return {}
