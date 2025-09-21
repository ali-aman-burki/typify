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
		from typify.inferencing.expression import TypeExpr
		  
		self.fobject = fobject
		self.caller = caller
		self.arguments = arguments
		self.returns = ReferenceSet()
		self.running = False

		self.params: dict[str, TypeExpr] = {
			k: TypeUtils.unify(v.refset).strip().remove_args()
			for k, v in arguments.items()
		}

	def __eq__(self, other):
		if not isinstance(other, CallSignature): return NotImplemented
		if self.fobject != other.fobject: return False
		return self.params == other.params

	def __hash__(self):
		return hash((self.fobject, frozenset(self.params.items())))

	def __repr__(self):
		parts = [f"{k}: {t}" for (k, t) in self.params.items()]
		return self.fobject.origin.parent.fqn + "(" + ", ".join(parts) + ")"

class CallStack:
	def __init__(self):
		self.stack: list[CallSignature] = []

	def push(self, signature: CallSignature):
		self.stack.append(signature)

	def pop(self) -> CallSignature:
		popped = self.stack.pop()
		return popped

	def contains(self, signature: CallSignature):
		return signature in self.stack

	def get(self, signature: CallSignature):
		for sig in self.stack:
			if sig == signature:
				return sig
		return signature