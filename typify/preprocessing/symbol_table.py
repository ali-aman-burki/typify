from __future__ import annotations
from pathlib import Path

import json
import ast

from typify.logging import logger

class ReferenceSet:

	def __init__(self, *reference_list: Instance):
		self.references = set(reference_list)
	
	def __repr__(self) -> str:
		return repr(self.as_type())
	
	def __len__(self) -> int:
		return len(self.references)
	
	def __contains__(self, item: Instance) -> bool:
		return item in self.references

	def __iter__(self):
		return iter(self.references)
	
	def copy(self):
		c = ReferenceSet()
		c.update(self)
		return c

	def add(self, reference: Instance):
		if isinstance(reference, int): print("shit")
		self.references.add(reference)
	
	def update(self, other: ReferenceSet):
		self.references.update(other.references)
	
	def ref(self) -> Instance | None:
		if len(self.references) != 1: logger.trace("Multiple references found where 1 was expected.")
		return next(iter(self.references))
	
	def as_type(self):
		from typify.inferencing.typeutils import TypeUtils
		return TypeUtils.unify(self)

class Symbol:
	def __init__(self, key: str):
		self.key = key
		self.packages: dict[str, Symbol] = {}
		self.modules: dict[str, Symbol] = {}
		self.classes: dict[str, Symbol] = {}
		self.functions: dict[str, Symbol] = {}
		self.names: dict[str, Symbol] = {}
		self.definitions: dict[str, DefinitionTable] = {}
		self.path_chain: list[Symbol] = []
		self.fqn = ""
		self.trust_annotations = False

		self.bases: list[Instance] = []
		self.mro: list[Instance] = []
		self.parameters = {}
		self.globals: set[ast.AST] = set()
		self.nonlocals: set[ast.AST] = set()
		self.parent: Symbol = None

		self.refset: ReferenceSet = ReferenceSet()

		self.origin: DefinitionTable = None
		self.tree: ast.FunctionDef | ast.AsyncFunctionDef = None
	
	def to_dict(self):
		from typify.inferencing.typeutils import TypeUtils

		data = {}
		if self.refset: data["type"] = repr(self.refset)
		if self.definitions: data["definitions"] = {key: value.to_dict() for key, value in self.definitions.items()}
		if self.globals: data["globals"] = list(self.globals)
		if self.packages: data["packages"] = {key: value.to_dict() for key, value in self.packages.items()}
		if self.modules: data["modules"] = {key: value.to_dict() for key, value in self.modules.items()}
		if self.bases: data["bases"] = [base.origin.parent.fqn for base in self.bases]
		if self.mro: data["mro"] = [instance.origin.parent.fqn for instance in self.mro]
		if self.nonlocals: data["nonlocals"] = list(self.nonlocals)
		if self.classes: data["classes"] = {key: value.to_dict() for key, value in self.classes.items()}
		if self.functions: data["functions"] = {key: value.to_dict() for key, value in self.functions.items()}
		if self.names: data["names"] = {key: value.to_dict() for key, value in self.names.items()}
		return data
	
	@staticmethod
	def transfer_names(source_names: dict[str, Name], destination: Symbol):
		for name in source_names.values():
			newname = Name(name.key)
			for old_def in name.definitions.values():
				newdef = DefinitionTable((old_def.module, old_def.position))
				newdef.refset.update(old_def.refset)
				newname.merge_def(newdef)
			destination.names[name.key] = newname
	
	def __str__(self): return self.fqn
	def __repr__(self): return self.fqn

	def export_to_json(self, file_path: Path):
		with file_path.open("w", encoding="utf-8") as f:
			json.dump(self.to_dict(), f, indent=4)

	def get_name(self, name: str) -> Name:
		nametable = self.names.get(name)
		if not nametable:
			nametable = Name(name)
			nametable.parent = self
			nametable.register_fqn()
			self.names[name] = nametable
		return nametable

	def get_class(self, name: str) -> Class:
		class_table = self.classes.get(name)
		if not class_table:
			class_table = Class(name)
			class_table.parent = self
			class_table.register_fqn()
			self.classes[name] = class_table
		return class_table
	
	def get_function(self, name: str) -> Function:
		function_table = self.functions.get(name)
		if not function_table:
			function_table = Function(name)
			function_table.parent = self
			function_table.register_fqn()
			self.functions[name] = function_table
		return function_table
	
	def set_package(self, package_table: "Package", fqn_map: dict[str, list[Symbol]]) -> "Package":
		self.packages[package_table.key] = package_table
		package_table.parent = self
		package_table.register_fqn(fqn_map)
		return package_table

	def set_module(self, module_table: Module, fqn_map: dict[str, list[Symbol]]) -> Module:
		self.modules[module_table.key] = module_table
		module_table.parent = self
		module_table.register_fqn(fqn_map)
		return module_table

	def new_def(self, deftable: DefinitionTable):
		deftable.parent = self
		self.definitions[deftable.key] = deftable
		return deftable
	
	def merge_def(self, deftable: DefinitionTable):
		if deftable.key in self.definitions: 
			self.definitions[deftable.key].refset.update(deftable.refset)
			return self.definitions[deftable.key]
		else: 
			return self.new_def(deftable)

	def get_enclosing_table(self):
		result = self.parent
		if isinstance(result, DefinitionTable):
			result = result.parent
		return result

	def get_enclosing_module(self):
		result = self
		while result and not isinstance(result, Module):
			result = result.get_enclosing_table()
		return result

	def get_enclosing_class(self):
		result = self
		while result and not isinstance(result, Class):
			result = result.get_enclosing_table()
		return result

	def get_latest_definition(self) -> Symbol | DefinitionTable:
		if not self.definitions: return self
		return next(reversed(self.definitions.values()))

	def register_fqn(self, fqn_map=None):
		parent = self.get_enclosing_table()
		self.fqn = parent.fqn + "." + self.key if parent.fqn else self.key
		if isinstance(self, Module) and self.key == "__init__": 
			self.fqn = parent.fqn
		self.path_chain = parent.path_chain + [self]
		if fqn_map is not None: fqn_map[self.fqn] = self.path_chain

	def set_function(self, function_table: Function) -> Function:
		self.functions[function_table.key] = function_table
		function_table.parent = self
		function_table.register_fqn()
		return function_table

	def set_name(self, name_table: Name) -> Name:
		self.names[name_table.key] = name_table
		name_table.parent = self
		name_table.register_fqn()
		return name_table
			
	def lookup_definition(self, defkey: tuple[Module, tuple[int, int]]) -> DefinitionTable:
		key = f"{defkey[0].fqn}:{defkey[1][0]}:{defkey[1][1]}"
		return self.definitions[key]
	
class Library(Symbol):
	def __init__(self, key):
		super().__init__(key)

class Package(Symbol):
	def __init__(self, key):
		super().__init__(key)

class Module(Symbol):
	def __init__(self, key):
		super().__init__(key)

class Class(Symbol):
	def __init__(self, key):
		super().__init__(key)

class Function(Symbol):
	def __init__(self, key):
		super().__init__(key)

class Name(Symbol):
	def __init__(self, key):
		super().__init__(key)

class CallFrame(Symbol):
	def __init__(self, key):
		super().__init__(key)

class Instance(Symbol):
	def __init__(self):
		super().__init__("typify@instance")
		from typify.inferencing.typeutils import TypeExpr
		self.type_expr: TypeExpr = None
		self.store: list[ReferenceSet] = []
	
	def __repr__(self):
		return self.label()

	def label(self):
		return f"instance@{repr(self.type_expr)}"
	
	def type_rep(self):
		return repr(self.type_expr)
	
class DefinitionTable(Symbol):
	def __init__(self, defkey: tuple[Symbol, tuple[int, int]]):
		super().__init__(f"{defkey[0].fqn}:{defkey[1][0]}:{defkey[1][1]}")
		self.module = defkey[0]
		self.position = defkey[1]