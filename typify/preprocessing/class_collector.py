import ast

from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.symbol_table import (
	 DefinitionTable,
	 Table,
	 ClassTable,
)

class TypeCollector(ast.NodeVisitor):
	def __init__(
			  self,
			  meta: ModuleMeta, 
			  symbol: Table,
			  tree: ast.AST,
		):
		self.meta = meta
		self.symbol = symbol
		self.tree = tree

	def collect(self): self.visit(self.tree)

	def visit_ClassDef(self, class_tree: ast.ClassDef):
		name = class_tree.name
		position = (class_tree.lineno, class_tree.col_offset)
		defkey = (self.meta.table, position)
		
		class_table = ClassTable(name)
		entering_symbol = class_table.add_definition(DefinitionTable(defkey))
		self.symbol.merge_class(class_table)
	
		TypeCollector(
			self.meta, 
			entering_symbol, 
			ast.Module(class_tree.body, type_ignores=[]),
		).collect()