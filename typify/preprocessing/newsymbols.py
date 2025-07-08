from __future__ import annotations

class Symbol:
	def __init__(self):
		super().__init__()
		self.name: str = None
		self.parent: Symbol = None

class _PackagingHolder:
	def __init__(self):
		super().__init__()
		self.packages: dict[str, Package] = {}
		self.modules: dict[str, Module] = {}
		self.trust_annotations: bool = False

class _SyntaxHolder:
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

class _FQNHolder:
	def __init__(self):
		super().__init__()
		self.fqn: str = None

class Library(
	_PackagingHolder,
	Symbol 
): 
	def __init__(self): super().__init__()

class Package(
	_FQNHolder, 
	_PackagingHolder,
	Symbol 
): 
	def __init__(self): super().__init__()

class Module(
	_FQNHolder,
	_SyntaxHolder,
	Symbol 
): 
	def __init__(self): super().__init__()

class ClassDefinition(
	_FQNHolder, 
	_SyntaxHolder, 
	_LocationHolder,
	Symbol 
): 
	def __init__(self): super().__init__()

class FunctionDefinition(
	_FQNHolder, 
	_SyntaxHolder, 
	_ReferenceHolder, 
	_LocationHolder,
	Symbol 
): 
	def __init__(self): super().__init__()

class NameDefinition(
	_FQNHolder, 
	_ReferenceHolder, 
	_LocationHolder,
	Symbol 
): 
	def __init__(self): super().__init__()

class Class(Symbol): 
	def __init__(self, name):
		super().__init__()
		self.name = name
		self.definitions: dict[str, ClassDefinition] = {}

class Function(Symbol): 
	def __init__(self, name):
		super().__init__()
		self.name = name
		self.definitions: dict[str, FunctionDefinition] = {}

class Name(Symbol): 
	def __init__(self, name):
		super().__init__()
		self.name = name
		self.definitions: dict[str, NameDefinition] = {}
