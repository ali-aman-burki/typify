import ast

class TypeAnnotation:
	def __eq__(self, value):
		return repr(self) == repr(value)

class UnresolvedType(TypeAnnotation):
	def __init__(self, identifier):
		self.identifier = identifier

	def __repr__(self):
		return "$unresolved$"

class Type(TypeAnnotation):
	def __init__(self, type_rep):
		self.type_rep = type_rep
	
	def __repr__(self):
		return str(self.type_rep)

class UnionType(TypeAnnotation):
	def __init__(self, types):
		self.types = types

	def __repr__(self):
		return f"Union[{', '.join(repr(t) for t in self.types)}]"

class ListType(TypeAnnotation):
	def __init__(self, element_type):
		self.element_type = element_type

	def __repr__(self):
		return f"List[{repr(self.element_type)}]"

class DictType(TypeAnnotation):
	def __init__(self, key_type, value_type):
		self.key_type = key_type
		self.value_type = value_type

	def __repr__(self):
		return f"Dict[{repr(self.key_type)}, {repr(self.value_type)}]"

class TupleType(TypeAnnotation):
	def __init__(self, element_types):
		self.element_types = element_types

	def __repr__(self):
		return f"Tuple[{', '.join(repr(t) for t in self.element_types)}]"

class SetType(TypeAnnotation):
	def __init__(self, element_type):
		self.element_type = element_type

	def __repr__(self):
		return f"Set[{repr(self.element_type)}]"

class OptionalType(TypeAnnotation):
	def __init__(self, element_type):
		self.element_type = element_type

	def __repr__(self):
		return f"Optional[{repr(self.element_type)}]"

class AnyType(TypeAnnotation):
	def __repr__(self):
		return "Any"