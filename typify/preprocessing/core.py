from pathlib import Path

from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.instance_utils import Instance
from typify.preprocessing.symbol_table import (
	Module,
	ClassDefinition,
	FunctionDefinition,
	CallFrame
)

class GlobalContext:
	libs: list[LibraryMeta]
	inference: dict[str, ModuleMeta] = {}
	sysmodules: dict[str, Instance] = {}
	symbol_map: dict[Module | ClassDefinition | FunctionDefinition, Instance | CallFrame] = {}
	function_object_map: dict[FunctionDefinition, Instance] = {}
	meta_map: dict[Module, ModuleMeta] = {}
	dependency_graph: dict[ModuleMeta, set[ModuleMeta]] = {}
	sequences: list[list[ModuleMeta]] = []

	path_index: dict[Path, ModuleMeta] = {}