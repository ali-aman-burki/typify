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
    def __init__(self):
        self.stack: list[CallSignature] = []
        self._recursion_counts: dict[tuple[Instance, CallSignature], int] = defaultdict(int)
        self._memo: dict[CallSignature, ReferenceSet] = {}
        self.recursion_limit: int = 1

    def push(self, signature: CallSignature):
        self.stack.append(signature)

    def pop(self) -> CallSignature:
        popped = self.stack.pop()
        if not any(s.fobject == popped.fobject for s in self.stack):
            self.clear_recursion_root(popped.fobject)
        return popped

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

    def current_recursion_root(self) -> Instance | None:
        if not self.stack:
            return None
        current_fobj = self.stack[-1].fobject
        count = sum(1 for s in self.stack if s.fobject == current_fobj)
        return current_fobj if count >= 2 else None

    def get_recursion_count(self, root: Instance, sig: CallSignature) -> int:
        return self._recursion_counts.get((root, sig), 0)

    def inc_recursion_count(self, root: Instance, sig: CallSignature) -> int:
        key = (root, sig)
        self._recursion_counts[key] = self._recursion_counts.get(key, 0) + 1
        return self._recursion_counts[key]

    def clear_recursion_root(self, root: Instance) -> None:
        to_del = [k for k in self._recursion_counts.keys() if k[0] == root]
        for k in to_del:
            self._recursion_counts.pop(k, None)

    def memo_get(self, sig: CallSignature) -> ReferenceSet | None:
        return self._memo.get(sig)

    def memo_set(self, sig: CallSignature, returns: ReferenceSet) -> None:
        self._memo[sig] = returns.copy()