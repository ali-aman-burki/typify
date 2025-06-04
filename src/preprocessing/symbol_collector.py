import ast
from src.symbol_table import VariableTable, ClassTable, FunctionTable, DefinitionTable
from src.builtins_ctn import builtins
from src.annotation_types import Type
from src.preprocessing.module_meta import ModuleMeta

class Collector(ast.NodeVisitor):
	def __init__(self, module_meta: ModuleMeta):
		self.library_table = module_meta.library_table
		self.module_table = module_meta.table
		self.current_table = self.module_table
		self.function_depth = 0

	def visit_ClassDef(self, node):
		enclosing_definition = self.current_table.get_latest_definition()
		class_name = node.name
		
		if class_name not in enclosing_definition.variables: enclosing_definition.add_variable(VariableTable(class_name))
		cvt = enclosing_definition.variables[class_name]
		cdvt = cvt.add_definition(DefinitionTable(cvt.generate_path(), node.lineno, node.col_offset))
		t = builtins.classes["type"]
		cdvt.type = Type(t)
		tinstnace = t.create_instance(t)
		cdvt.points_to.append(tinstnace)

		if class_name not in enclosing_definition.classes:
			class_table = ClassTable(class_name)
			enclosing_definition.add_class(class_table)
		else:
			class_table = enclosing_definition.classes[class_name]

		cd = class_table.add_definition(DefinitionTable(class_table.generate_path(), node.lineno, node.col_offset))
		tinstnace.returns.append(cd)

		self.current_table = class_table
		self.generic_visit(node)
		self.current_table = self.current_table.get_enclosing_table()

	def visit_AsyncFunctionDef(self, node):
		return self.visit_FunctionDef(node)

	def visit_FunctionDef(self, node):
		enclosing_definition = self.current_table.get_latest_definition()
		function_name = node.name

		if function_name not in enclosing_definition.variables: enclosing_definition.add_variable(VariableTable(function_name))
		
		fvt = enclosing_definition.variables[function_name]
		fdvt = fvt.add_definition(DefinitionTable(fvt.generate_path(), node.lineno, node.col_offset))
		f = builtins.classes["function"]
		fdvt.type = Type(f)
		finstance = f.create_instance(f)
		fdvt.points_to.append(finstance)

		if function_name not in enclosing_definition.functions:
			function_table = FunctionTable(function_name)
			enclosing_definition.add_function(function_table)
		else:
			function_table = enclosing_definition.functions[function_name]
		
		fdt = function_table.add_definition(DefinitionTable(function_table.generate_path(), node.lineno, node.col_offset))
		fdt.tree = node
		finstance.returns.append(fdt)

	def visit_AnnAssign(self, node):
		if isinstance(node.target, ast.Tuple):
			for element in node.target.elts:
				if isinstance(element, ast.Name):
					self.process_variable(element.id, element.lineno, element.col_offset)
		else:
			if isinstance(node.target, ast.Name): self.process_variable(node.target.id, node.target.lineno, node.target.col_offset)
		self.generic_visit(node)

	def visit_Assign(self, node):
		for target in node.targets:
			if isinstance(target, ast.Tuple):
				for element in target.elts:
					if isinstance(element, ast.Name):
						self.process_variable(element.id, element.lineno, element.col_offset)
			else:
				if isinstance(target, ast.Name): self.process_variable(target.id, target.lineno, target.col_offset)
		self.generic_visit(node)
	
	def process_variable(self, name, lineno, col_offset):
		if name not in self.current_table.get_latest_definition().variables:
			v = self.current_table.get_latest_definition().add_variable(VariableTable(name))
			v.add_definition(DefinitionTable(v.generate_path(), lineno, col_offset))
		else:
			v = self.current_table.get_latest_definition().variables[name]
			v.add_definition(DefinitionTable(v.generate_path(), lineno, col_offset))