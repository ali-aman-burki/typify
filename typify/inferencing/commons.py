from dataclasses import dataclass

from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.libs import RequiredLibs

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

@dataclass
class ArgTuple:
	refset: ReferenceSet
	defkey: tuple[Module, tuple[int, int]]

@dataclass
class Context:
	libs: dict[str, LibraryMeta]
	sysmodules: dict[str, Instance]
	symbol_map: dict[Module | ClassDefinition | FunctionDefinition, Instance]
	function_object_map: dict[FunctionDefinition, Instance]
	meta_map: dict[Module, ModuleMeta]

class ConstantObjects:
	
	i_dict = {
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
			result = TypeUtils.instantiate(Builtins.get_type(type_name))
			ConstantObjects.i_dict[type_name] = result
		return result
	
class Builtins:

	@staticmethod
	def module() -> Module:
		try:
			result = RequiredLibs.preloaded["builtinlib"].library_table.modules["builtins"]
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
			result = RequiredLibs.preloaded["stdlib"].library_table.modules["typing"]
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
