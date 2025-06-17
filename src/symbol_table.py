import json
from pathlib import Path
from collections import defaultdict
import ast

class Table:
	def __init__(self, key: str):
		self.key = key
		self.packages: dict[str, Table] = {}
		self.modules: dict[str, Table] = {}
		self.classes: dict[str, Table] = {}
		self.functions: dict[str, Table] = {}
		self.variables: dict[str, Table] = {}
		self.definitions: dict[Table, dict[str, DefinitionTable]] = {}
		self.instances: list[Table] = []

		self.bases: list = []
		self.params: list = []
		self.globals: set[ast.AST] = set()
		self.nonlocals: set[ast.AST] = set()
		self.parent: Table = None

		self.kind: str = ""
		self.type = None
		self.points_to: set[Table] = set()
		self.origin: DefinitionTable = None
		self.template_used: Table = None
		self.tree: ast.FunctionDef = None		

	def to_dict(self):
		data = {}
		if self.type: data["type"] = repr(self.type)
		if self.definitions:
			data["definitions"] = {}
			for m in self.definitions:
				subdict = self.definitions[m]
				for k, v in subdict.items():
					data["definitions"][k] = v.to_dict()
		if self.globals: data["globals"] = list(self.globals)
		if self.packages: data["packages"] = {key: value.to_dict() for key, value in self.packages.items()}
		if self.modules: data["modules"] = {key: value.to_dict() for key, value in self.modules.items()}
		if self.bases: data["bases"] = [base.key if isinstance(base, Table) else "$unresolved$" for base in self.bases]
		if self.nonlocals: data["nonlocals"] = list(self.nonlocals)
		if self.classes: data["classes"] = {key: value.to_dict() for key, value in self.classes.items()}
		if self.functions: data["functions"] = {key: value.to_dict() for key, value in self.functions.items()}
		if self.variables: data["variables"] = {key: value.to_dict() for key, value in self.variables.items()}
		return data
	
	@staticmethod
	def transfer_content(src: "Table", dst: "Table"):
		dst.variables.update(src.variables)
	
	@staticmethod
	def process_group(key: str, values: list["Table"], defkey: tuple["Table", tuple[int, int]], precedence: list["ModuleTable"]) -> "Table":
		from src.typeutils import TypeUtils

		var = VariableTable(key)
		var.add_definition(DefinitionTable(defkey[0], defkey[1]))

		for table in values:
			tdef = table.get_latest_definition(defkey, precedence)
			var.points_to.update(tdef.points_to)
		
		return var

	@staticmethod
	def homogenize(dicts: list[dict[str, "Table"]], defkey: tuple["Table", tuple[int, int]], precedence: list["ModuleTable"]) -> dict[str, "Table"]:
		key_groups = defaultdict(list)

		for d in dicts:
			for key, value in d.items():
				key_groups[key].append(value)

		result = {}
		for key, values in key_groups.items():
			result[key] = Table.process_group(key, values, defkey, precedence)

		return result
	
	def get_type_class(self):
		if isinstance(self, DefinitionTable):
			if isinstance(self.parent, ClassTable):
				return self.parent
		elif isinstance(self, ClassTable):
			return self
		else:
			return None
	
	def __str__(self):
		path = self.generate_path()
		if self.key == "__init__": return ("" if not path or path == "builtins" else path)
		return ("" if not path or path == "builtins" else path + ".") + self.key

	def export_to_json(self, file_path: Path):
		with file_path.open("w", encoding="utf-8") as f:
			json.dump(self.to_dict(), f, indent=4)

	def fully_qualified_file_name(self):
		path = self.generate_path()
		return ("" if not path or path == "builtins" else path + ".") + self.key

	def fully_qualified_name(self):
		path = self.generate_path()
		if self.key == "__init__": return ("" if not path or path == "builtins" else path)
		return ("" if not path or path == "builtins" else path + ".") + self.key

	def generate_path(self):
		path = []
		current_table = self
		while current_table and not isinstance(current_table, LibraryTable):
			if isinstance(current_table, (ModuleTable, PackageTable)) and current_table != self:
				path.append(current_table.key)
			current_table = current_table.get_enclosing_table()
		return ".".join(path[::-1])
	
	def get_path_chain(self) -> list["Table"]:
		path_chain = []
		current_table = self
		while current_table and current_table:
			if isinstance(current_table, (ModuleTable, PackageTable, LibraryTable)):
				path_chain.append(current_table)
			current_table = current_table.get_enclosing_table()
		return list(reversed(path_chain[::-1]))

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

	def get_latest_definition(self, anchor: tuple["ModuleTable", tuple[int, int]] = None, precedence: list["ModuleTable"] = None) -> "DefinitionTable":
		if not self.definitions:
			return self

		if anchor is None:
			last_module_dict = next(reversed(self.definitions.values()))
			return next(reversed(last_module_dict.values()))

		anchor_module, (anchor_line, anchor_col) = anchor

		if precedence:
			if anchor_module not in precedence:
				return self

			candidates = [m for m in precedence if m in self.definitions and precedence.index(m) <= precedence.index(anchor_module)]
		else:
			candidates = list(self.definitions.keys())

		for module in reversed(candidates):
			defs = self.definitions[module]

			if module == anchor_module:
				prior_defs = [
					defn for defn in defs.values()
					if defn.position < (anchor_line, anchor_col)
				]
				if prior_defs:
					return prior_defs[-1]
			else:
				return next(reversed(defs.values()))

		return self

	def add_package(self, package_table) -> "PackageTable":
		self.packages[package_table.key] = package_table
		package_table.parent = self
		return package_table

	def add_module(self, module_table) -> "ModuleTable":
		self.modules[module_table.key] = module_table
		module_table.parent = self
		return module_table

	def add_class(self, class_table) -> "ClassTable":
		self.classes[class_table.key] = class_table
		class_table.parent = self
		return class_table

	def add_function(self, function_table) -> "FunctionTable":
		self.functions[function_table.key] = function_table
		function_table.parent = self
		return function_table

	def override_variable(self, variable_table) -> "VariableTable":
		self.variables[variable_table.key] = variable_table
		variable_table.parent = self
		return variable_table

	def add_definition(self, definition_table: "DefinitionTable") -> "DefinitionTable":
		if definition_table.module not in self.definitions:
			self.definitions[definition_table.module] = {}

		self.definitions[definition_table.module][definition_table.key] = definition_table
			 
		definition_table.parent = self
		return definition_table

	def lookup_definition(self, defkey: tuple["ModuleTable", tuple[int, int]]) -> "DefinitionTable":
		mtable, (line, col) = defkey
		if mtable in self.definitions:
			for defn in self.definitions[mtable].values():
				if defn.position == (line, col):
					return defn
		return None

	def order_definitions(self, module_precedence: list["ModuleTable"]) -> dict["ModuleTable", dict[str, "DefinitionTable"]]:
		ordered_definitions = {}
    
		for mtable in module_precedence:
			if mtable in self.definitions:
				ordered_subdict = dict(
					sorted(self.definitions[mtable].items(), key=lambda item: item[1].position)
				)
				ordered_definitions[mtable] = ordered_subdict

		self.definitions = ordered_definitions
		return self.definitions
	
	def add_variable(self, variable_table: "VariableTable"):
		if variable_table.key in self.variables:
			for topdict in variable_table.definitions.values():
				for d in topdict.values():
					self.variables[variable_table.key].add_definition(d)
					d.parent = self.variables[variable_table.key]
			return self.variables[variable_table.key]
		else:
			return self.override_variable(variable_table)
	
class LibraryTable(Table):
	def __init__(self, key):
		self.module_object_map: dict[ModuleTable | PackageTable, InstanceTable] = {}
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
	def __init__(self, module: Table, position: tuple[int, int]):
		super().__init__(f"{module.fully_qualified_name()}:{position[0]}:{position[1]}")
		self.module = module
		self.position = position