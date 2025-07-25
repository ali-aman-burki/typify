from dataclasses import dataclass

from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.core import Global
from typify.preprocessing.instance_utils import (
	Instance,
	ReferenceSet
) 
from typify.preprocessing.symbol_table import (
    ClassDefinition, 
	FunctionDefinition,
    Module
)

@dataclass
class ParameterEntry:
	name: str
	refset: ReferenceSet
	defkey: tuple[Module, tuple[int, int]]

	is_vararg: bool = False
	is_kwarg: bool = False
	is_kwonly: bool = False
	is_posonly: bool = False

	annotation: Instance = None

@dataclass
class ArgTuple:
	refset: ReferenceSet
	defkey: tuple[Module, tuple[int, int]]

@dataclass
class Context:
	libs: list[LibraryMeta]
	sysmodules: dict[str, Instance]
	symbol_map: dict[Module | ClassDefinition | FunctionDefinition, Instance]
	function_object_map: dict[FunctionDefinition, Instance]
	meta_map: dict[Module, ModuleMeta]

class ConstantObjects:
	
	i_dict: dict[str, Instance] = {
		"int": None,
		"float": None,
		"complex": None,
		"str": None,
		"bytes": None,
		"bool": None,
		"NoneType": None,
		"ellipsis": None
	}

	@staticmethod
	def get(type_name: str):
		from typify.inferencing.typeutils import TypeUtils
		result = ConstantObjects.i_dict.get(type_name, None)
		if not result:
			result = TypeUtils.instantiate_with_args(Builtins.get_type(type_name))
			ConstantObjects.i_dict[type_name] = result
		else:
			result.update_type_info(Builtins.get_type(type_name))
		return result

class Checker:
	@staticmethod
	def match_origin(lhs: ClassDefinition, rhs: ClassDefinition):
		return lhs and lhs == rhs

class Builtins:

	@staticmethod
	def module() -> Module:
		try:
			result = Global.inference["builtins"].table
			return result
		except Exception:
			return None
	
	@staticmethod
	def get_type(type_name: str) -> ClassDefinition | None:
		try: 
			result = Builtins.module().classes[type_name].get_latest_definition()
			return result
		except Exception: 
			return None
class Typing:
	
	@staticmethod
	def module() -> Module:
		try:
			result = Global.inference["typing"].table
			return result
		except Exception:
			return None
	
	@staticmethod
	def get_type(type_name: str) -> ClassDefinition | None:
		try: 
			result = Typing.module().classes[type_name].get_latest_definition()
			return result
		except Exception: 
			return None 
