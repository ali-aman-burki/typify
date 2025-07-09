from __future__ import annotations

import ast

from typify.preprocessing.instance_utils import (
    ReferenceSet,
	Instance
)
from typify.inferencing.commons import ParameterEntry

class _PathHolder:
	def __init__(self):
		super().__init__()
		self.pathchain: list[Package | Module] = []

class _PackagingHolder:
	def __init__(self):
		super().__init__()
		self.packages: dict[str, Package] = {}
		self.modules: dict[str, Module] = {}
		self.trust_annotations: bool = False

class _SyntaxingHolder:
	def __init__(self):
		super().__init__()
		self.classes: dict[str, Class] = {}
		self.functions: dict[str, Function] = {}
		self.names: dict[str, Name] = {}

class _LocationHolder:
	def __init__(self):
		super().__init__()
		self.defkey: tuple[Module, tuple[int, int]] = None

class _ReferenceHolder:
	def __init__(self):
		super().__init__()
		self.refset: ReferenceSet = ReferenceSet()

class Symbol:
	def __init__(self, id: str):
		super().__init__()
		self.id: str = id
		self.fqn: str = ""
		self.parent: Symbol = None
	
	def __repr__(self): return self.fqn if self.fqn else self.id
	def __str__(self): return self.fqn if self.fqn else self.id

	def to_dict(self):
		return {}
	
	def get_enclosing_symbol(self):
		result = self.parent
		if isinstance(result, (ClassDefinition, FunctionDefinition)):
			result = result.parent
		return result
	
	def get_enclosing_module(self):
		result = self
		while result and not isinstance(result, Module):
			result = result.get_enclosing_symbol()
		return result
	
	def get_latest_definition(self) -> Symbol:
		return self

class _PackagingSymbol(
	Symbol, 
	_PathHolder,
	_PackagingHolder
):
	def __init__(self, id: str):
		super().__init__(id)

	def to_dict(self):
		data = super().to_dict()
		data["packages"] = {key: value.to_dict() for key, value in self.packages.items()}
		data["modules"] = {key: value.to_dict() for key, value in self.modules.items()}
		return data

	def set_package(self, package: Package, fqn_map: dict):
		self.packages[package.id] = package
		package.parent = self
		package.fqn = f"{self.fqn}.{package.id}" if self.fqn else package.id
		package.pathchain = self.pathchain + [package]
		fqn_map[self.fqn] = self.pathchain

	def set_module(self, module: Module, fqn_map):
		self.modules[module.id] = module
		module.parent = self
		module.fqn = f"{self.fqn}.{module.id}" if self.fqn else module.id
		if module.id == "__init__": module.fqn = self.fqn
		module.pathchain = self.pathchain + [module]
		fqn_map[self.fqn] = self.pathchain

class _SyntaxingSymbol(
	Symbol, 
	_SyntaxingHolder
):
	def __init__(self, id: str):
		super().__init__(id)

	def to_dict(self):
		data = super().to_dict()
		data["classes"] = {key: value.to_dict() for key, value in self.classes.items()}
		data["functions"] = {key: value.to_dict() for key, value in self.functions.items()}
		data["names"] = {key: value.to_dict() for key, value in self.names.items()}
		return data

	def get_name(self, id: str) -> Name:
		name = self.names.get(id)
		if not name:
			name = Name(id)
			name.parent = self
			name.fqn = f"{self.fqn}.{id}" if self.fqn else id
			self.names[id] = name
		return name

	def get_class(self, id: str) -> Class:
		cls = self.classes.get(id)
		if not cls:
			cls = Class(id)
			cls.parent = self
			cls.fqn = f"{self.fqn}.{id}" if self.fqn else id
			self.classes[id] = cls
		return cls

	def get_function(self, id: str) -> Function:
		func = self.functions.get(id)
		if not func:
			func = Function(id)
			func.parent = self
			func.fqn = f"{self.fqn}.{id}" if self.fqn else id
			self.functions[id] = func
		return func

class _LocatableSymbol(
	_SyntaxingSymbol, 
	_LocationHolder
):
	def __init__(self, defkey: tuple[Module, tuple[int, int]]):
		super().__init__(f"{defkey[0].fqn}:{defkey[1][0]}:{defkey[1][1]}")
		self.defkey = defkey

class Library(_PackagingSymbol): pass
class Package(_PackagingSymbol): pass
class Module(
	_SyntaxingSymbol, 
	_PathHolder
): pass

class ClassDefinition(_LocatableSymbol): 
	def __init__(self, defkey: tuple[Module, tuple[int, int]]):
		super().__init__(defkey)
		self.bases: list[Instance]
		self.mro: list[Instance]
	
	def to_dict(self):
		data = super().to_dict()
		data["bases"] = [base.origin.fqn for base in self.bases]
		data["mro"] = [base.origin.fqn for base in self.mro]
		return data

class FunctionDefinition(
	_LocatableSymbol, 
	_ReferenceHolder
):
	def __init__(self, defkey: tuple[Module, tuple[int, int]]):
		super().__init__(defkey)
		self.tree: ast.FunctionDef | ast.AsyncFunctionDef = None
		self.parameters: dict[str, ParameterEntry] = {}
	
	def to_dict(self):
		data = super().to_dict()
		data["return_type"] = repr(self.refset.as_type())
		return data

class NameDefinition(
	_LocatableSymbol, 
	_ReferenceHolder
):
	def to_dict(self):
		data = super().to_dict()
		data["type"] = repr(self.refset.as_type())
		return data

class CallFrame(
	_SyntaxingSymbol, 
	_ReferenceHolder
): pass
	
class Class(Symbol): 
	def __init__(self, id):
		super().__init__(id)
		self.definitions: dict[str, ClassDefinition] = {}
	
	def to_dict(self):
		data = super().to_dict()
		data["definitions"] = {key: value.to_dict() for key, value in self.definitions.items()}
		return data

	def set_definition(self, class_def: ClassDefinition):
		class_def.parent = self
		class_def.fqn = self.fqn
		self.definitions[class_def.id] = class_def
		return class_def
		
	def get_latest_definition(self) -> ClassDefinition:
		if not self.definitions: return self
		return next(reversed(self.definitions.values()))

class Function(Symbol): 
	def __init__(self, id):
		super().__init__(id)
		self.definitions: dict[str, FunctionDefinition] = {}
	
	def to_dict(self):
		data = super().to_dict()
		data["definitions"] = {key: value.to_dict() for key, value in self.definitions.items()}
		return data
	
	def set_definition(self, func_def: FunctionDefinition):
		func_def.parent = self
		func_def.fqn = self.fqn
		self.definitions[func_def.id] = func_def
		return func_def

	def merge_definition(self, func_def: FunctionDefinition):
		if func_def.id in self.definitions: 
			self.definitions[func_def.id].refset.update(func_def.refset)
			return self.definitions[func_def.id]
		else: 
			return self.set_definition(func_def)
		
	def get_latest_definition(self) -> FunctionDefinition:
		if not self.definitions: return self
		return next(reversed(self.definitions.values()))

class Name(Symbol): 
	def __init__(self, id):
		super().__init__(id)
		self.definitions: dict[str, NameDefinition] = {}
	
	def to_dict(self):
		data = super().to_dict()
		data["definitions"] = {key: value.to_dict() for key, value in self.definitions.items()}
		return data
	
	def set_definition(self, name_def: NameDefinition):
		name_def.parent = self
		name_def.fqn = self.fqn
		self.definitions[name_def.id] = name_def
		return name_def

	def merge_definition(self, func_def: NameDefinition):
		if func_def.id in self.definitions: 
			self.definitions[func_def.id].refset.update(func_def.refset)
			return self.definitions[func_def.id]
		else: 
			return self.set_definition(func_def)
		
	def get_latest_definition(self) -> NameDefinition:
		if not self.definitions: return self
		return next(reversed(self.definitions.values()))
	
	def lookup_definition(self, defkey: tuple[Module, tuple[int, int]]) -> NameDefinition:
		key = f"{defkey[0].fqn}:{defkey[1][0]}:{defkey[1][1]}"
		return self.definitions[key]

def test_pathchain_and_fqn():
    lib = Library("rootlib")  # fqn will remain ""
    pkg1 = Package("pkg1")
    pkg2 = Package("pkg2")
    mod1 = Module("mod1")
    mod2 = Module("__init__")

    # Register the hierarchy
    lib.set_package(pkg1, {})
    pkg1.set_package(pkg2, {})
    pkg2.set_module(mod1, {})
    pkg2.set_module(mod2, {})

    # Assert FQNs
    assert lib.fqn == ""
    assert pkg1.fqn == "pkg1"
    assert pkg2.fqn == "pkg1.pkg2"
    assert mod1.fqn == "pkg1.pkg2.mod1"
    assert mod2.fqn == "pkg1.pkg2"  # __init__ special case

    # Assert pathchains
    assert lib.pathchain == []
    assert pkg1.pathchain == [pkg1]
    assert pkg2.pathchain == [pkg1, pkg2]
    assert mod1.pathchain == [pkg1, pkg2, mod1]
    assert mod2.pathchain == [pkg1, pkg2, mod2]

    # Verify object types in pathchain
    assert all(isinstance(x, (Package, Module)) for x in mod1.pathchain)

    print("✅ Pathchain and FQN logic tests passed.")

# Run the test
# test_pathchain_and_fqn()
