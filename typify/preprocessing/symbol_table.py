from __future__ import annotations
import json
import ast

from pathlib import Path

class Table:
	def __init__(self, key: str):
		self.key = key
		self.packages: dict[str, Table] = {}
		self.modules: dict[str, Table] = {}
		self.classes: dict[str, Table] = {}
		self.functions: dict[str, Table] = {}
		self.names: dict[str, Table] = {}
		self.definitions: dict[str, DefinitionTable] = {}
		self.instances: list[Table] = []
		self.path_chain: list[Table] = []
		self.fqn = ""
		self.trust_annotations = False

		self.bases: list = []
		self.parameters = {}
		self.globals: set[ast.AST] = set()
		self.nonlocals: set[ast.AST] = set()
		self.parent: Table = None

		self.kind: str = ""
		self.points_to: set[InstanceTable] = set()
		self.origin: DefinitionTable = None
		self.tree: ast.FunctionDef = None		

	def to_dict(self):
		from typify.inferencing.typeutils import TypeUtils

		data = {}
		if self.points_to: data["type"] = repr(TypeUtils.unify([pt.type_expr for pt in self.points_to]))
		if self.definitions: data["definitions"] = {key: value.to_dict() for key, value in self.definitions.items()}
		if self.globals: data["globals"] = list(self.globals)
		if self.packages: data["packages"] = {key: value.to_dict() for key, value in self.packages.items()}
		if self.modules: data["modules"] = {key: value.to_dict() for key, value in self.modules.items()}
		if self.bases: data["bases"] = [base.key if isinstance(base, Table) else "$unresolved$" for base in self.bases]
		if self.nonlocals: data["nonlocals"] = list(self.nonlocals)
		if self.classes: data["classes"] = {key: value.to_dict() for key, value in self.classes.items()}
		if self.functions: data["functions"] = {key: value.to_dict() for key, value in self.functions.items()}
		if self.names: data["names"] = {key: value.to_dict() for key, value in self.names.items()}
		return data
	
	@staticmethod
	def transfer_names(source_names: dict[str, NameTable], destination: Table):
		destination.names.update(source_names)

	@staticmethod
	def create_and_transfer_names(
			source: Table, 
			destination: Table, 
			defkey: tuple[ModuleTable, tuple[int, int]],
		) -> dict[str, NameTable]:
		names = {}
		for modvar in source.names.values():
			modvardef = modvar.get_latest_definition()
			vartable = NameTable(modvar.key)
			vardef = vartable.add_definition(DefinitionTable(defkey))
			vardef.points_to.update(modvardef.points_to)
			names[vartable.key] = vartable = destination.merge_name(vartable)
		
		return names
	
	def __str__(self): return self.fqn
	def __repr__(self): return self.fqn

	def export_to_json(self, file_path: Path):
		with file_path.open("w", encoding="utf-8") as f:
			json.dump(self.to_dict(), f, indent=4)

	def override_name(self, nametable: NameTable):
		self.names[nametable.key] = nametable

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

	def get_latest_definition(self) -> Table | DefinitionTable:
		if not self.definitions: return self
		return next(reversed(self.definitions.values()))

	def register_fqn(self, fqn_map=None):
		parent = self.get_enclosing_table()
		self.fqn = parent.fqn + "." + self.key if parent.fqn else self.key
		if isinstance(self, ModuleTable) and self.key == "__init__": 
			self.fqn = parent.fqn
		self.path_chain = parent.path_chain + [self]
		if fqn_map is not None: fqn_map[self.fqn] = self.path_chain

	def set_package(self, package_table: "PackageTable", fqn_map: dict[str, list[Table]]) -> "PackageTable":
		self.packages[package_table.key] = package_table
		package_table.parent = self
		package_table.register_fqn(fqn_map)
		return package_table

	def set_module(self, module_table: ModuleTable, fqn_map: dict[str, list[Table]]) -> ModuleTable:
		self.modules[module_table.key] = module_table
		module_table.parent = self
		module_table.register_fqn(fqn_map)
		return module_table

	def set_class(self, class_table: ClassTable) -> ClassTable:
		self.classes[class_table.key] = class_table
		class_table.parent = self
		class_table.register_fqn()
		return class_table

	def set_function(self, function_table: FunctionTable) -> FunctionTable:
		self.functions[function_table.key] = function_table
		function_table.parent = self
		function_table.register_fqn()
		return function_table

	def set_name(self, name_table: NameTable) -> NameTable:
		self.names[name_table.key] = name_table
		name_table.parent = self
		name_table.register_fqn()
		return name_table

	def merge_class(self, class_table: ClassTable) -> ClassTable:
		if class_table.key in self.classes:
			for d in class_table.definitions.values():
				self.classes[class_table.key].add_definition(d)
				d.parent = self.classes[class_table.key]
			return self.classes[class_table.key]
		else:
			return self.set_class(class_table)
	
	def merge_function(self, function_table: FunctionTable) -> FunctionTable:
		if function_table.key in self.functions:
			for d in function_table.definitions.values():
				self.functions[function_table.key].add_definition(d)
				d.parent = self.functions[function_table.key]
			return self.functions[function_table.key]
		else:
			return self.set_function(function_table)

	def merge_name(self, name_table: NameTable, merge_def=False) -> NameTable:
		if name_table.key in self.names:
			for d in name_table.definitions.values():
				if merge_def: self.names[name_table.key].merge_definition(d)
				else: self.names[name_table.key].add_definition(d)
				d.parent = self.names[name_table.key]
			return self.names[name_table.key]
		else:
			return self.set_name(name_table)

	def add_definition(self, definition_table: DefinitionTable) -> DefinitionTable:
		self.definitions[definition_table.key] = definition_table
		definition_table.parent = self
		definition_table.fqn = self.fqn
		return definition_table

	def merge_definition(self, definition_table: DefinitionTable) -> DefinitionTable:
		if definition_table.key in self.definitions:
			self.definitions[definition_table.key].points_to.update(definition_table.points_to)
			return self.definitions[definition_table.key]
		else:
			return self.add_definition(definition_table)
			
	def lookup_definition(self, defkey: tuple[ModuleTable, tuple[int, int]]) -> DefinitionTable:
		mtable, (line, col) = defkey
		if mtable in self.definitions:
			for defn in self.definitions[mtable].values():
				if defn.position == (line, col):
					return defn
		return None
	
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

class NameTable(Table):
	def __init__(self, key):
		super().__init__(key)

class CallFrameTable(Table):
	def __init__(self, key):
		super().__init__(key)

class InstanceTable(Table):
	def __init__(self):
		super().__init__("typify@instance")
		from typify.inferencing.typeutils import TypeExpr
		self.type_expr: TypeExpr = None
		self.store: list[set[InstanceTable]] = []
	
	def label(self):
		return f"instance@{repr(self.type_expr)}"
	
	def type_rep(self):
		return repr(self.type_expr)
	
	def __repr__(self):
		return self.label()
	
class DefinitionTable(Table):
	def __init__(self, defkey: tuple[Table, tuple[int, int]]):
		super().__init__(f"{defkey[0].fqn}:{defkey[1][0]}:{defkey[1][1]}")
		self.module = defkey[0]
		self.position = defkey[1]