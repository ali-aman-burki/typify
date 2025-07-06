from dataclasses import dataclass, field

from typify.preprocessing.symbol_table import DefinitionTable, ReferenceSet
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.commons import ArgTuple

@dataclass(eq=False)
class CallSignature:
	function_table: DefinitionTable
	arguments: dict[str, ArgTuple]
	returns: ReferenceSet = field(default_factory=ReferenceSet)
	snapshot: list[set[str]] = field(default_factory=list)
	running: bool = False
	stabilized: bool = False

	def __eq__(self, other):
		if not isinstance(other, CallSignature): return NotImplemented
		if self.function_table != other.function_table: return False
		if self.arguments.keys() != other.arguments.keys(): return False

		for key in self.arguments:
			t1 = TypeUtils.unify(self.arguments[key].refset)
			t2 = TypeUtils.unify(other.arguments[key].refset)
			if t1 != t2: return False

		return True

	def __hash__(self):
		param_fingerprint = tuple(
			sorted(
				(k, TypeUtils.unify(v.refset))
				for k, v in self.arguments.items()
			)
		)
		return hash((self.function_table, param_fingerprint))

	def __repr__(self):
		args = []
		for arg in self.arguments.values():
			args.append(TypeUtils.unify(arg.refset))
		joined = ", ".join(repr(arg) for arg in args)
		return self.function_table.parent.key + f"({joined})"

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

	def get(self, sig: CallSignature) -> CallSignature | None:
		index = self.index_map.get(sig)
		if index is not None:
			return self.stack[index]
		return None

	def trace(self, sig: CallSignature) -> list[CallSignature]:
		index = self.index_map.get(sig)
		if index is not None:
			return self.stack[index:]
		return []