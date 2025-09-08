from __future__ import annotations

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
		root: CallSignature,
	):
		self.fobject = fobject
		self.caller = caller
		self.arguments = arguments
		self.returns = returns
		self.root = root
		self.running = False

		if self.root:
			root_param_map = dict(self.root._param_fp)

			self._param_fp = tuple(
				(k, TypeUtils.unify(v.refset).strip().remove_nested(root_param_map.get(k), 0))
				for k, v in arguments.items()
			)
		else:
			self._param_fp = tuple(
				(k, TypeUtils.unify(v.refset).strip())
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
		self._root_map: dict[Instance, CallSignature] = {}
		self._depth_map: dict[Instance, int] = {}
	
	def push(self, signature: CallSignature):
		fobj = signature.fobject
		if fobj in self._root_map:
			self._depth_map[fobj] += 1
		else:
			if signature.root is None:
				signature.root = signature
			self._root_map[fobj] = signature
			self._depth_map[fobj] = 1
		self.stack.append(signature)
	
	def pop(self) -> CallSignature:
		sig = self.stack.pop()
		fobj = sig.fobject
		if fobj in self._depth_map:
			self._depth_map[fobj] -= 1
			if self._depth_map[fobj] <= 0:
				self._depth_map.pop(fobj, None)
				self._root_map.pop(fobj, None)
		return sig
	
	def contains(self, signature: CallSignature):
		return signature in self.stack

	def get(self, signature: CallSignature):
		for sig in self.stack:
			if sig == signature:
				return sig

		if signature.root is None and signature.fobject in self._root_map:
			signature.root = self._root_map[signature.fobject]
		return signature
