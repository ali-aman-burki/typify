from dataclasses import dataclass

from typify.preprocessing.symbol_table import DefinitionTable
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.commons import ArgTuple

@dataclass(eq=False)
class CallSignature:
	function_table: DefinitionTable
	arguments: dict[str, ArgTuple]

	def __eq__(self, other):
		if not isinstance(other, CallSignature): return NotImplemented
		if self.function_table != other.function_table: return False
		if self.arguments.keys() != other.arguments.keys(): return False

		for key in self.arguments:
			t1 = TypeUtils.unify(self.arguments[key].points_to)
			t2 = TypeUtils.unify(other.arguments[key].points_to)
			if t1 != t2: return False

		return True

	def __hash__(self):
		param_fingerprint = tuple(
			sorted(
				(k, TypeUtils.unify(v.points_to))
				for k, v in self.arguments.items()
			)
		)
		return hash((self.function_table, param_fingerprint))


class CallStack:
	def __init__(self):
		self.stack: list[CallSignature] = []
		self.index_map: dict[CallSignature, int] = {}

	def push(self, sig: CallSignature):
		self.stack.append(sig)
		self.index_map[sig] = len(self.stack) - 1

	def pop(self) -> CallSignature:
		sig = self.stack.pop()
		self.index_map.pop(sig, None)
		return sig

	def contains(self, sig: CallSignature) -> bool:
		return sig in self.index_map

	def trace(self, sig: CallSignature) -> list[CallSignature]:
		index = self.index_map.get(sig)
		if index is not None:
			return self.stack[index:]
		return []

