from typify.preprocessing.instance_utils import ReferenceSet, Instance
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.commons import ArgTuple

class CallSignature:
    def __init__(
			self, 
			fobject: Instance, 
			caller: Instance, 
			arguments: dict[str, ArgTuple], 
			returns: ReferenceSet, 
			running: bool = False
		):
        self.fobject = fobject
        self.caller = caller
        self.arguments = arguments
        self.returns = returns
        self.running = running

        self._param_fp = tuple(
			(k, TypeUtils.unify(v.refset).strip().remove_typenest())
			for k, v in arguments.items()
        )
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