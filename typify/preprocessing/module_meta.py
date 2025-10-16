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

	def precollect(self, typeslots: bool, infer: bool):
		from typify.preprocessing.precollector import PreCollector
		try:
			PreCollector(self, typeslots, infer).visit(self.tree)
		except (RecursionError, UnicodeError):
			pass	
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
			self.vslots[position][4].update(refset)
		
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
			self.fslots[position][5][argname] = refset
		
		self.fslots_snapshots[position][0][argname] = refset

	def safe_update_fslot_return(self, position: tuple[int, int], refset):
		from typify.preprocessing.instance_utils import ReferenceSet

		refset: ReferenceSet = refset

		if self.fslots:
			self.fslots[position][6] = refset
		
		self.fslots_snapshots[position][1] = refset

	def __repr__(self):
		return self.table.fqn
	
	def typeslots(self):
		from typify.preprocessing.precollector import PreCollector
		from typify.preprocessing.instance_utils import ReferenceSet
		from typify.inferencing.commons import Typing, Checker

		def type_filter(refset: ReferenceSet, preinferred: str) -> str:
			inferred = refset.typestring() if refset else preinferred

			if inferred == PreCollector.UNVISITED and not preinferred:
				return ""

			if not preinferred:
				return inferred

			if inferred == preinferred or preinferred == PreCollector.UNVISITED: 
				return inferred

			type_expr = refset.as_type()

			if Checker.match_origin(type_expr.base, Typing.get_type("Union")):
				repr_args = [repr(arg) for arg in type_expr.args]
				if preinferred in repr_args:
					return inferred
				return f"Union[{preinferred}, {', '.join(repr_args)}]"

			return f"Union[{preinferred}, {inferred}]"

		data = {
			"variables": {},
			"functions": {}
		}

		for key, value in self.vslots.items():
			name_value = value[0] 
			type_value = type_filter(value[4], value[1])
			
			result_key = f"{value[2]}:{key[0]}:{key[1]}"
			result_value = {
				"name": name_value,
				"type": type_value
			}
			data["variables"][result_key] = result_value

		for key, value in self.fslots.items():
			result_key = f"{value[4]}:{key[0]}:{key[1]}"

			fdef_value = value[0]
			fqn_value = value[1]

			parameters_value = {
				pname: type_filter(ptype, value[2][pname])
				for pname, ptype in value[5].items()
			}

			return_type_value = type_filter(value[6], value[3])
			
			result_value = PreCollector.build_function_signature(
				fdef_value, 
				fqn_value, 
				parameters_value, 
				return_type_value
			)
			data["functions"][result_key] = result_value
			
		return data