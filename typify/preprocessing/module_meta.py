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
		self.vslots_snapshots: dict[tuple[int, int], ReferenceSet] = {}
		self.fslots_snapshots: dict[tuple[int, int], list[dict[str, ReferenceSet] | ReferenceSet]] = {}

		self.count_map: dict[tuple[int, int], int] = {}

	def precollect(self, typeslots: bool):
		from typify.preprocessing.precollector import PreCollector
		PreCollector(self, typeslots).visit(self.tree)
		return sum(self.count_map.values())

	def snapshot(self) -> tuple[dict, dict]:
		hashable_funcslots = {}
		for position, funcstuff in self.fslots_snapshots.items():
			h_params = {}
			for p, r in funcstuff[0].items():
				h_params[p] = r.as_type()
			h_returns = funcstuff[1].as_type()

			hashable_funcslots[position] = (h_params, h_returns)
		
		hashable_varsots = {}
		for position, varstuff in self.vslots_snapshots.items():
			hashable_varsots[position] = varstuff.as_type()

		return (hashable_varsots, hashable_funcslots)

	def update_count_map(self, position: tuple[int, int]):
		from typify.preprocessing.core import GlobalContext
		if self.count_map[position] > 0:
			self.count_map[position] -= 1
			GlobalContext.progress_bar.update()

	def safe_update_vslot(self, position: tuple[int, int], refset):
		from typify.preprocessing.instance_utils import ReferenceSet

		refset: ReferenceSet = refset
		
		if self.vslots:
			if isinstance(self.vslots[position][1], ReferenceSet):
				self.vslots[position][1].update(refset)
			else:
				self.vslots[position][1] = refset
		
		if position in self.vslots_snapshots:
			self.vslots_snapshots[position].update(refset)
		else:
			self.vslots_snapshots[position] = refset
	
	def register_fslot(self, position: tuple[int, int]):
		from typify.preprocessing.instance_utils import ReferenceSet

		if position not in self.fslots_snapshots:
			self.fslots_snapshots[position] = [{}, ReferenceSet()]

	def safe_update_fslot_args(self, position: tuple[int, int], argname: str, refset):
		from typify.preprocessing.instance_utils import ReferenceSet

		refset: ReferenceSet = refset

		if self.fslots:
			self.fslots[position][2][argname] = refset
		
		self.fslots_snapshots[position][0][argname] = refset

	def safe_update_fslot_return(self, position: tuple[int, int], refset):
		from typify.preprocessing.instance_utils import ReferenceSet

		refset: ReferenceSet = refset

		if self.fslots:
			self.fslots[position][3] = refset
		
		self.fslots_snapshots[position][1] = refset

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
			value[1] = value[1].typestring() if isinstance(value[1], ReferenceSet) else value[1]
			k = f"{value[2]}:{key[0]}:{key[1]}"
			v = {
				"name": value[0],
				"type": value[1],
				"node": value[3] 
			}
			data["variables"][k] = v

		for key, value in self.fslots.items():
			value = value.copy()
			k = f"{value[4]}:{key[0]}:{key[1]}"

			value[2] = value[2].copy()
			for x, y in value[2].items():
				value[2][x] = y.typestring() if isinstance(value[2][x], ReferenceSet) else value[2][x]
			
			value[3] = value[3].typestring() if isinstance(value[3], ReferenceSet) else value[3]
			
			v = PreCollector.build_function_signature(value[0], value[1], value[2], value[3])
			data["functions"][k] = v
			
		return data


