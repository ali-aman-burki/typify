from collections import defaultdict

from typify.preprocessing.instance_utils import ReferenceSet, Instance
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.commons import ArgTuple

class CallSignature:
	def __init__(
		self, 
		fobject: Instance, 
		caller: Instance, 
		arguments: dict[str, ArgTuple], 
	):
		from typify.preprocessing.core import GlobalContext

		self.fobject = fobject
		self.caller = caller
		self.arguments = arguments
		self.returns = ReferenceSet()
		self.running = False

		lineage_params = [dict(sig._param_fp) for sig in GlobalContext.call_stack.lineage()]
		
		accum_lineage = defaultdict(list)
		for d in lineage_params:
			for k, v in d.items():
				accum_lineage[k].append(v)

		pairs = []
		for k, v in arguments.items():
			current = TypeUtils.unify(v.refset).strip()
			originals = accum_lineage[k]
			updated = current

			for original in originals:
				updated = current.remove_nested(original)
				if updated != current:
					break
			pairs.append((k, updated))
		self._param_fp = tuple(pairs)

		self._fp = (self.fobject, self._param_fp)

	def __eq__(self, other):
		if not isinstance(other, CallSignature): return NotImplemented
		return self._fp == other._fp

	def __hash__(self):
		return hash(self._fp)

	def __repr__(self):
		parts = [f"{k}: {t}" for (k, t) in self._param_fp]
		return self.fobject.origin.parent.fqn + "(" + ", ".join(parts) + ")"

class CallStack:
	def __init__(self, *, max_per_fobject: int = 2):
		self.stack: list[CallSignature] = []
		self.max_per_fobject = max_per_fobject

	def count_fobject(self, fobject) -> int:
		return sum(1 for sig in self.stack if sig.fobject == fobject)

	def push(self, signature: CallSignature):
		self.stack.append(signature)

	def pop(self) -> CallSignature:
		return self.stack.pop()
	
	def contains(self, signature: CallSignature):
		return signature in self.stack

	def get(self, signature: CallSignature):
		for sig in self.stack:
			if sig == signature:
				return sig
		return signature

	def lineage(self) -> list[CallSignature]:
		if not self.stack: return []
		current = self.stack[-1]
		return [sig for sig in self.stack if sig.fobject == current.fobject]