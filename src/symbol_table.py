import json
from pathlib import Path
import ast
from src.contanier_types import TypeAnnotation
import copy

class Table:
	def __init__(self, key: str):
		self.key = key
		self.packages: dict[str, Table] = {}
		self.modules: dict[str, Table] = {}
		self.classes: dict[str, Table] = {}
		self.functions: dict[str, Table] = {}
		self.variables: dict[str, Table] = {}
		self.instance_variables: dict[str, Table] = {}
		self.definitions: dict[str, Table] = {}
		self.instances: list[Table] = []

		self.imports: list[ast.AST] = []
		self.bases: list = []
		self.params: list = []
		self.globals: ast.AST = set()
		self.nonlocals: ast.AST = set()
		self.parent: Table = None

		self.collected_types: list[TypeAnnotation] = []
		self.type: TypeAnnotation = None
		self.points_to: list[Table] = []
		self.returns: list[Table] = []
		self.template_used: Table = None

	def copy(self):
		new_table = Table(self.key)

		new_table.packages = {k: v.copy() for k, v in self.packages.items()}
		new_table.modules = {k: v.copy() for k, v in self.modules.items()}
		new_table.classes = {k: v.copy() for k, v in self.classes.items()}
		new_table.functions = {k: v.copy() for k, v in self.functions.items()}
		new_table.variables = {k: v.copy() for k, v in self.variables.items()}
		new_table.instance_variables = {k: v.copy() for k, v in self.instance_variables.items()}
		new_table.definitions = {k: v.copy() for k, v in self.definitions.items()}
		new_table.instances = [inst.copy() for inst in self.instances]
		new_table.points_to = {pt.copy() for pt in self.points_to}
		new_table.imports = copy.deepcopy(self.imports)
		new_table.bases = copy.deepcopy(self.bases)
		new_table.params = copy.deepcopy(self.params)
		new_table.globals = copy.deepcopy(self.globals)
		new_table.nonlocals = copy.deepcopy(self.nonlocals)
		new_table.type = self.type
		return new_table

	def to_dict(self):
		data = {}
		if self.type: data["type"] = repr(self.type)
		if self.definitions: data["definitions"] = {key: value.to_dict() for key, value in self.definitions.items()}
		if self.globals: data["globals"] = list(self.globals)
		if self.packages: data["packages"] = {key: value.to_dict() for key, value in self.packages.items()}
		if self.modules: data["modules"] = {key: value.to_dict() for key, value in self.modules.items()}
		if self.imports: data["imports"] = [ast.unparse(import_node) for import_node in self.imports]
		if self.bases: data["bases"] = [base.key if isinstance(base, Table) else "$unresolved$" for base in self.bases]
		if self.nonlocals: data["nonlocals"] = list(self.nonlocals)
		if self.classes: data["classes"] = {key: value.to_dict() for key, value in self.classes.items()}
		if self.functions: data["functions"] = {key: value.to_dict() for key, value in self.functions.items()}
		if self.variables: data["variables"] = {key: value.to_dict() for key, value in self.variables.items()}
		if self.instance_variables: data["instance_variables"] = {key: value.to_dict() for key, value in self.instance_variables.items()}
		return data
	
	def get_type_class(self):
		if isinstance(self, DefinitionTable):
			if isinstance(self.parent, ClassTable):
				return self.parent
		elif isinstance(self, ClassTable):
			return self
		else:
			return None
	
	def create_instance(self, template_def):
		instance = InstanceTable(self.key)
		instance.template_used = template_def
		for var in template_def.variables.values():
			nv = VariableTable(var.key)
			instance.add_variable(nv)
		
		template_def.instances.append(instance)
		return instance

	def __str__(self):
		path = self.generate_path()
		return path + "." + self.key if path != "builtins" else self.key

	def export_to_json(self, directory: Path, file_name: str):
		directory.mkdir(parents=True, exist_ok=True)
		file_path = directory / f"{file_name}.json"
		with file_path.open("w", encoding="utf-8") as f:
			json.dump(self.to_dict(), f, indent=4)

	def generate_path(self):
		path = []
		current_table = self
		while current_table and not isinstance(current_table, LibraryTable):
			if isinstance(current_table, (ModuleTable, PackageTable)):
				path.append(current_table.key)
			current_table = current_table.get_enclosing_table()
		return ".".join(path[::-1])
	
	def get_enclosing_table(self):
		result = self.parent
		if isinstance(result, DefinitionTable):
			result = result.parent
		return result

	def get_enclosing_module(self):
		result = self
		while result and not isinstance(result, ModuleTable):
			result = result.get_enclosing_table()
		return result

	def get_enclosing_class(self):
		result = self
		while result and not isinstance(result, ClassTable):
			result = result.get_enclosing_table()
		return result

	def get_latest_definition(self):
		return next(reversed(self.definitions.values())) if self.definitions else self

	def add_package(self, package_table):
		self.packages[package_table.key] = package_table
		package_table.parent = self
		return package_table

	def add_module(self, module_table):
		self.modules[module_table.key] = module_table
		module_table.parent = self
		return module_table

	def add_class(self, class_table):
		self.classes[class_table.key] = class_table
		class_table.parent = self
		return class_table

	def add_function(self, function_table):
		self.functions[function_table.key] = function_table
		function_table.parent = self
		return function_table

	def add_variable(self, variable_table):
		self.variables[variable_table.key] = variable_table
		variable_table.parent = self
		return variable_table
	
	def add_instance_variable(self, variable_table):
		self.instance_variables[variable_table.key] = variable_table
		variable_table.parent = self
		return variable_table

	def add_definition(self, definition_table):
		self.definitions[definition_table.key] = definition_table
		definition_table.parent = self
		return definition_table
	
class LibraryTable(Table):
	def __init__(self, key):
		super().__init__(key)

class PackageTable(Table):
	def __init__(self, key):
		super().__init__(key)

class ModuleTable(Table):
	def __init__(self, key):
		super().__init__(key)

class ClassTable(Table):
	def __init__(self, key):
		super().__init__(key)

class FunctionTable(Table):
	def __init__(self, key):
		super().__init__(key)

class VariableTable(Table):
	def __init__(self, key):
		super().__init__(key)

class InstanceTable(Table):
	def __init__(self, key):
		super().__init__(key)

class DefinitionTable(Table):
	def __init__(self, path, line, column):
		super().__init__(f"{path}:{line}:{column}")
		self.path = path
		self.line = line
		self.column = column
	
	def parse(key):
		data = key.split(":")
		path = data[0]
		line = int(data[1])
		column = int(data[2])
		return DefinitionTable(path, line, column)