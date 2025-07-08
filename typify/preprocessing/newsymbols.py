from __future__ import annotations
import ast

class Symbol:
	def __init__(self, id: str):
		super().__init__()
		self.id: str = id
		self.fqn: str = id
		self.parent: Symbol = None

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
		self.refset = None

class _PackagingSymbol(
	Symbol, 
	_PackagingHolder
):
	def __init__(self, id: str):
		super().__init__(id)

	def set_package(self, package: Package):
		self.packages[package.id] = package
		package.parent = self
		package.fqn = f"{self.fqn}.{package.id}" if self.fqn else package.id
		package.path_chain = package.parent.path_chain + [package]

	def set_module(self, module: Module):
		self.modules[module.id] = module
		module.parent = self
		module.fqn = f"{self.fqn}.{module.id}" if self.fqn else module.id
		module.path_chain = module.parent.path_chain + [module]

class _SyntaxingSymbol(
	Symbol, 
	_SyntaxingHolder
):
	def __init__(self, id: str):
		super().__init__(id)

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

class _TypeableSymbol(
	_LocatableSymbol, 
	_ReferenceHolder
): pass

class Library(_PackagingSymbol): pass
class Package(_PackagingSymbol): pass
class Module(_SyntaxingSymbol): pass

class ClassDefinition(_LocatableSymbol): pass
class NameDefinition(_TypeableSymbol): pass

class FunctionDefinition(_TypeableSymbol):
	def __init__(self, defkey: tuple[Module, tuple[int, int]]):
		super().__init__(defkey)
		self.tree: ast.FunctionDef | ast.AsyncFunctionDef = None

class Class(Symbol): 
	def __init__(self, id):
		super().__init__(id)
		self.definitions: dict[str, ClassDefinition] = {}

class Function(Symbol): 
	def __init__(self, id):
		super().__init__(id)
		self.definitions: dict[str, FunctionDefinition] = {}

class Name(Symbol): 
	def __init__(self, id):
		super().__init__(id)
		self.definitions: dict[str, NameDefinition] = {}

def test_symbol_structure():
    lib = Library("lib")
    pkg = Package("pkg")
    mod = Module("mod")

    lib.set_package(pkg)
    pkg.set_module(mod)

    assert lib.id == "lib"
    assert pkg.id == "pkg"
    assert mod.id == "mod"

    assert lib.packages["pkg"] is pkg
    assert pkg.modules["mod"] is mod

    assert pkg.parent is lib
    assert pkg.fqn == "lib.pkg"
    assert mod.parent is pkg
    assert mod.fqn == "lib.pkg.mod"

    # Module symbol accessors
    class_sym = mod.get_class("MyClass")
    func_sym = mod.get_function("my_func")
    name_sym = mod.get_name("x")

    assert class_sym.id == "MyClass"
    assert func_sym.id == "my_func"
    assert name_sym.id == "x"

    assert class_sym.fqn == "lib.pkg.mod.MyClass"
    assert func_sym.fqn == "lib.pkg.mod.my_func"
    assert name_sym.fqn == "lib.pkg.mod.x"

    # ClassDefinition test
    defkey = (mod, (10, 4))
    class_def = ClassDefinition(defkey)

    assert class_def.defkey == defkey
    assert isinstance(class_def.id, str)
    assert class_def.id == "lib.pkg.mod:10:4"

    # FunctionDefinition test
    func_def = FunctionDefinition(defkey)
    assert func_def.defkey == defkey
    assert hasattr(func_def, "refset")
    assert func_def.id == "lib.pkg.mod:10:4"

    # NameDefinition test
    name_def = NameDefinition(defkey)
    assert name_def.defkey == defkey
    assert hasattr(name_def, "refset")
    assert name_def.id == "lib.pkg.mod:10:4"

    print("✅ All symbol construction and linking tests passed.")

# Run test
test_symbol_structure()

