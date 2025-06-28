from __future__ import annotations


from typify.preprocessing.symbol_table import (
	InstanceTable, 
	DefinitionTable
)
from typify.inferencing.commons import Typing

class TypeUtils:

	@staticmethod
	def instantiate(
		typedef: DefinitionTable, 
		typeargs: list[InstanceTable] | None = None
		) -> InstanceTable:

		instance = InstanceTable()
		TypeUtils.correct_instance_type(instance, typedef, typeargs)
		return instance

	@staticmethod
	def correct_instance_type(
		instance: InstanceTable,
		typedef: DefinitionTable, 
		typeargs: list[InstanceTable] | None = None
		):

		typeargs = typeargs if typeargs else []
		instance.typedef = typedef
		#init typevars from typedef

		TypeUtils.update_typevars(instance.typevars, typeargs) 
		fqn = typedef.parent.fqn if typedef else "$unresolved$"
		instance.key = f"instance@{fqn}"

	@staticmethod
	def update_typevars(
		typevars: dict[InstanceTable, InstanceTable], 
		typeargs: list[InstanceTable]
	) -> None:
		existing_keys = list(typevars.keys())
		
		for i in range(len(typeargs)):
			key = TypeUtils.get_safe(
				existing_keys, 
				i, 
				TypeUtils.instantiate(Typing.get_type("TypeVar"))
			)
			typevars[key] = typeargs[i]

	@staticmethod
	def get_safe(lst, index, default=None):
		return lst[index] if 0 <= index < len(lst) else default