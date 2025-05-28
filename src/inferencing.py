import ast
from src.symbol_table import *
from src.context import Context
from src.annotation_parser import AnnotationParser
from src.contanier_types import Type
from src.builtins_ctn import builtins
from src.typeutils import TypeUtils

import json
import copy
from pathlib import Path

class Analyzer(ast.NodeVisitor):
	def __init__(self, library_table: Table, module_table: Table):
		self.library_table = library_table
		self.module_table = module_table
		self.current_table = module_table

		self.type_data = {
			"vassignments": {},
			"functions": {}
		}

	def visit_Import(self, node):
		self.current_table.get_latest_definition().imports.append(node)
		self.generic_visit(node)

	def visit_ImportFrom(self, node):
		self.current_table.get_latest_definition().imports.append(node)
		self.generic_visit(node)

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
		finstance.returns.append(fdt)

		self.type_data["functions"][(fdt.line, fdt.column)] = (function_name, Type(builtins.classes["NoneType"]))

		self.current_table = function_table
		self.generic_visit(node)
		self.current_table = self.current_table.get_enclosing_table()

	def visit_Return(self, node):
		ct = self.current_table
		mt = self.module_table
		lt = self.library_table
		
		context = Context(lt, mt, ct)
		function_name = self.current_table.key
		enclosing_definition = self.current_table.get_enclosing_table().get_latest_definition()

		ft = enclosing_definition.functions[function_name]
		fdt = ft.get_latest_definition()

		type_bundle = context.resolve_type(node.value)
		
		fdt.collected_types.append(type_bundle[0])
		fdt.points_to += type_bundle[1]
		fdt.type = TypeUtils.unify([t for t in fdt.collected_types])
		fdt.return_nodes.append(node.value)

		self.type_data["functions"][(fdt.line, fdt.column)] = (function_name, fdt.type)

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
		
		annotated_type_bundle = (annotated_type := AnnotationParser(context).visit(node.annotation), TypeUtils.instantiate(annotated_type))
		inferred_type_bundle = context.resolve_type(node.value)

		eventual_bundle = TypeUtils.select_more_resolved_type(annotated_type_bundle, inferred_type_bundle)

		nd = None

		if lhs:
			nd = lhs.add_definition(DefinitionTable(lhs.generate_path(), node.lineno, node.col_offset))
			nd.type = eventual_bundle[0]
			nd.points_to = eventual_bundle[1]

		self.type_data["vassignments"][(nd.line, nd.column)] = (node.target, nd.type if nd else "$unresolved$")
		self.generic_visit(node)

	def visit_Assign(self, node):
		ct = self.current_table
		mt = self.module_table
		lt = self.library_table
		context = Context(lt, mt, ct)
		inf = context.resolve_type(node.value)

		for target in node.targets:
			nd = None
			if isinstance(target, ast.Tuple):
				pass
			else:
				lhs = context.verify_lhs(target)
				if lhs:
					nd = lhs.add_definition(DefinitionTable(lhs.generate_path(), node.lineno, node.col_offset))
					nd.type = inf[0]
					nd.points_to = inf[1]
				
				self.type_data["vassignments"][(nd.line, nd.column)] = (target, nd.type if nd else "$unresolved$")
		self.generic_visit(node)
	
	def visit_AugAssign(self, node):
		toAssign = ast.Assign(
			targets=[node.target],
			value=ast.BinOp(
				left=copy.deepcopy(node.target),
				op=node.op,
				right=node.value
			)
		)
		ast.copy_location(toAssign, node)
		ast.copy_location(toAssign.value, node)

		toAssign = ast.fix_missing_locations(toAssign)

		self.visit_Assign(toAssign)

	def export_type_data(self, directory: Path, file_name: str):
		directory.mkdir(parents=True, exist_ok=True)
		file_path = directory / f"{file_name}.json"
		output_data = {
			"vassignments": {},
			"functions": {}
		}
		for key, value in self.type_data["vassignments"].items():
			lhs = ast.unparse(value[0]) 
			inf_type = value[1]
			output_data["vassignments"][f"{key[0]}:{key[1]}"] = f"{lhs}: {inf_type}"
		
		for key, value in self.type_data["functions"].items():
			func_name, func_type = value
			output_data["functions"][f"{key[0]}:{key[1]}"] = f"{func_name}() -> {func_type}"
		with file_path.open("w", encoding="utf-8") as f:
			json.dump(output_data, f, indent='\t')
