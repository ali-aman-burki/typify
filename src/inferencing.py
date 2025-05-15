import ast
from src.symbol_table import *
from src.context import Context
from src.annotation_converter import AnnotationConverter

class Analyzer(ast.NodeVisitor):
	def __init__(self, library_table: Table, module_table: Table):
		self.library_table = library_table
		self.module_table = module_table
		self.current_table = module_table

		self.unresolved = {}

	def visit_Import(self, node):
		self.current_table.get_latest_definition().imports.append(node)
		self.generic_visit(node)

	def visit_ImportFrom(self, node):
		self.current_table.get_latest_definition().imports.append(node)
		self.generic_visit(node)

	def visit_ClassDef(self, node):
		enclosing_definition = self.current_table.get_latest_definition()
		class_name = node.name
		if class_name not in enclosing_definition.classes:
			class_table = ClassTable(class_name)
			enclosing_definition.add_class(class_table)
		else:
			class_table = enclosing_definition.classes[class_name]
		class_table.add_definition(DefinitionTable(class_table.generate_path(), node.lineno, node.col_offset))
		self.current_table = class_table
		self.generic_visit(node)
		self.current_table = self.current_table.get_enclosing_table()

	def visit_AsyncFunctionDef(self, node):
		return self.visit_FunctionDef(node)

	def visit_FunctionDef(self, node):
		enclosing_definition = self.current_table.get_latest_definition()
		function_name = node.name
		if function_name not in enclosing_definition.functions:
			function_table = FunctionTable(function_name)
			enclosing_definition.add_function(function_table)
		else:
			function_table = enclosing_definition.functions[function_name]
		function_table.add_definition(DefinitionTable(function_table.generate_path(), node.lineno, node.col_offset))
		self.current_table = function_table
		self.generic_visit(node)
		self.current_table = self.current_table.get_enclosing_table()

	def visit_Return(self, node):
		self.generic_visit(node)

	def visit_Global(self, node):
		self.current_table.globals.update(node.names)
		self.generic_visit(node)

	def visit_Nonlocal(self, node):
		self.current_table.nonlocals.update(node.names)
		self.generic_visit(node)

	def visit_Call(self, node):
		self.generic_visit(node)

	def visit_AnnAssign(self, node):
		ct = self.current_table
		mt = self.module_table
		lt = self.library_table
		context = Context(lt, mt, ct)

		lhs = context.verify_lhs(node.target)
		if lhs:
			nd = lhs.add_definition(DefinitionTable(lhs.generate_path(), node.lineno, node.col_offset))
			nd.type = AnnotationConverter().visit(node.annotation)
		self.generic_visit(node)

	def visit_Assign(self, node):
		ct = self.current_table
		mt = self.module_table
		lt = self.library_table
		context = Context(lt, mt, ct)
		rhs_type = context.resolve_type(node.value)

		for target in node.targets:
			if isinstance(target, ast.Tuple):
				pass
			else:
				lhs = context.verify_lhs(target)
				if lhs and rhs_type:
					nd = lhs.add_definition(DefinitionTable(lhs.generate_path(), node.lineno, node.col_offset))
					nd.type = rhs_type
				else:
					self.unresolved[(target.lineno, target.col_offset)] = (context, lhs if lhs else target, rhs_type if rhs_type else node.value)
		self.generic_visit(node)