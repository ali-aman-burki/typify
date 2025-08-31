import ast

from pathlib import Path

from typify.preprocessing.symbol_table import Module

class ModuleMeta:

	def __init__(
			self, 
			src: Path, 
			tree: ast.Module, 
			trust_annotations: bool,
			last_modified: Path
		):
		from typify.preprocessing.instance_utils import ReferenceSet
		self.src = src
		self.tree = tree
		self.table = Module(src.stem)
		self.trust_annotations = trust_annotations
		self.last_modified = last_modified

		self.vslots: dict[tuple[int, int], list[str | ReferenceSet]] = {}
		self.fslots: dict[tuple[int, int], list[ast.FunctionDef | ast.AsyncFunctionDef | str | dict[str, ReferenceSet] | ReferenceSet]] = {}

	def __repr__(self):
		return self.table.fqn
	
	def typeslots(self):
		from typify.preprocessing.instance_utils import ReferenceSet
		from typify.preprocessing.precollector import PreCollector

		data = {
			"variables": {},
			"functions": {}
		}

		for key, value in self.vslots.items():
			value = value.copy()
			value[1] = value[1].as_type().strip() if isinstance(value[1], ReferenceSet) else value[1]
			k = f"{value[2]}:{key[0]}:{key[1]}"
			v = {
				"name": value[0],
				"type": f"{value[1]}",
				"node": value[3] 
			}
			data["variables"][k] = v

		for key, value in self.fslots.items():
			value = value.copy()
			k = f"{value[4]}:{key[0]}:{key[1]}"

			value[2] = value[2].copy()
			for x, y in value[2].items():
				value[2][x] = repr(y.as_type().strip()) if isinstance(value[2][x], ReferenceSet) else value[2][x]
			
			value[3] = repr(value[3].as_type().strip()) if isinstance(value[3], ReferenceSet) else value[3]
			
			v = PreCollector.build_function_signature(value[0], value[1], value[2], value[3])
			data["functions"][k] = v
			
		return data


