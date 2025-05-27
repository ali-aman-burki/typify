import ast

from src.builtins_ctn import builtins

class TypeAnnotation:
	def __eq__(self, value):
		return repr(self) == repr(value)

class UnresolvedType(TypeAnnotation):
	def __init__(self, identifier):
		self.identifier = identifier

	def __repr__(self):
		return "$unresolved$"

class Type(TypeAnnotation):
	def __init__(self, type_def):
		self.type_def = type_def
	
	def __repr__(self):
		return str(self.type_def.get_type_class())

class UnionType(TypeAnnotation):
	def __init__(self, types):
		self.types = types

	def __repr__(self):
		return f"{' | '.join(repr(t) for t in self.types)}"

class ListType(TypeAnnotation):
	def __init__(self, element_type):
		self.element_type = element_type
		self.type_def = builtins.classes["list"]

	def __repr__(self):
		return f"list[{repr(self.element_type)}]"

class DictType(TypeAnnotation):
	def __init__(self, key_type, value_type):
		self.key_type = key_type
		self.value_type = value_type
		self.type_def = builtins.classes["dict"]

	def __repr__(self):
		return f"dict[{repr(self.key_type)}, {repr(self.value_type)}]"

class TupleType(TypeAnnotation):
	def __init__(self, element_types):
		self.element_types = element_types
		self.type_def = builtins.classes["tuple"]

	def __repr__(self):
		return f"tuple[{', '.join(repr(t) for t in self.element_types)}]"

class SetType(TypeAnnotation):
	def __init__(self, element_type):
		self.element_type = element_type
		self.type_def = builtins.classes["set"]

	def __repr__(self):
		return f"set[{repr(self.element_type)}]"

class OptionalType(TypeAnnotation):
	def __init__(self, element_type):
		self.element_type = element_type

	def __repr__(self):
		return f"Optional[{repr(self.element_type)}]"

class AnyType(TypeAnnotation):
	def __repr__(self):
		return "Any"