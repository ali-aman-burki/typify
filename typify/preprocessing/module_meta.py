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
		from typify.preprocessing.instance_utils import VSlot, FSlot
		
		self.src = src
		self.tree = tree
		self.table = Module(src.stem)
		self.trust_annotations = trust_annotations
		self.last_modified = last_modified

		try:
			self.source_text = src.read_text(encoding="utf8")
			self.source_lines = self.source_text.splitlines()
		except Exception:
			self.source_text = ""
			self.source_lines = []

		self.vslots: dict[tuple[int, int], VSlot] = {}
		self.fslots: dict[tuple[int, int], FSlot] = {}
		self.vslots_snapshots: dict[tuple[int, int], VSlot] = {}
		self.fslots_snapshots: dict[tuple[int, int], FSlot] = {}

		self.count_map: dict[tuple[int, int], int] = {}

	def precollect(self, typeslots: bool, infer: bool, topn: int):
		from typify.preprocessing.precollector import PreCollector
		try:
			PreCollector(self, typeslots, infer, topn).visit(self.tree)
		except (RecursionError, UnicodeError):
			pass	
		return sum(self.count_map.values())

	def snapshot(self) -> tuple[dict, dict]:
		hashable_funcslots = {}
		for position, funcstuff in self.fslots_snapshots.items():
			hashed_params = {}
			for p, r in funcstuff.u_params.items():
				hashed_params[p] = r.as_type()
			hashed_returns = funcstuff.u_ret.as_type()

			hashable_funcslots[position] = (hashed_params, hashed_returns)
		
		hashable_varsots = {}
		for position, varstuff in self.vslots_snapshots.items():
			hashable_varsots[position] = varstuff.u_type.as_type()

		return (hashable_varsots, hashable_funcslots)

	def update_count_map(self, position: tuple[int, int]):
		from typify.preprocessing.core import GlobalContext
		if self.count_map[position] > 0:
			self.count_map[position] -= 1
			GlobalContext.progress_bar.update()

	def register_vslot(
			self, 
			position: tuple[int, int],
			vslot
		):
		
		if position not in self.vslots: 
			self.vslots[position] = vslot
	
	def register_vslot_snapshot(
			self, 
			position: tuple[int, int],
			vslot
		):
		
		if position not in self.vslots_snapshots: 
			self.vslots_snapshots[position] = vslot

	def register_fslot(
			self, 
			position: tuple[int, int],
			fslot
		):
		
		if position not in self.fslots: 
			self.fslots[position] = fslot

	def register_fslot_snapshot(
			self, 
			position: tuple[int, int], 
			fslot
		):

		if position not in self.fslots_snapshots:
			self.fslots_snapshots[position] = fslot

	def safe_update_vslot(self, position: tuple[int, int], refset):
		from typify.preprocessing.instance_utils import ReferenceSet

		refset: ReferenceSet = refset
		
		if self.vslots:
			self.vslots[position].u_type.update(refset)
		
		self.vslots_snapshots[position].u_type.update(refset)

	def safe_update_fslot_args(self, position: tuple[int, int], argname: str, refset):
		from typify.preprocessing.instance_utils import ReferenceSet

		refset: ReferenceSet = refset

		if self.fslots:
			self.fslots[position].u_params[argname] = refset
		
		self.fslots_snapshots[position].u_params[argname] = refset

	def safe_update_fslot_return(self, position: tuple[int, int], refset):
		from typify.preprocessing.instance_utils import ReferenceSet

		refset: ReferenceSet = refset

		if self.fslots:
			self.fslots[position].u_ret = refset
		
		self.fslots_snapshots[position].u_ret = refset

	def __repr__(self):
		return self.table.fqn
	
	def typeslots(self, key: str):
		buckets = []

		for position, vslot in self.vslots.items():
			u_type = [vslot.u_type.typestring()] if vslot.u_type else []
			buckets.append({
				"category": "variable",
				"scope": vslot.scope,
				"name": vslot.name,
				"type": u_type + vslot.h_type,
				"locations": [[position[0], position[1]]]
			})
		
		for position, fslot in self.fslots.items():
			u_ret = [fslot.u_ret.typestring()] if fslot.u_ret else []
			buckets.append({
				"category": "return",
				"scope": f"{fslot.scope + '.' if fslot.scope else ''}{fslot.name}",
				"name": fslot.name,
				"type": u_ret + fslot.h_ret,
				"locations": [[position[0], position[1]]]
			})

			for param_name, u_param in fslot.u_params.items():
				param_type = [u_param.typestring()] if u_param else []
				buckets.append({
					"category": "argument",
					"scope": f"{fslot.scope + '.' if fslot.scope else ''}{fslot.name}",
					"name": param_name,
					"type": param_type + fslot.h_params.get(param_name, []),
					"locations": [[position[0], position[1]]]
				})

		return {
			key: buckets
		}