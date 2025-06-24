from typify.preprocessing.dependency_utils import DependencyBundle
from typify.inferencing.executor import (
    Context,
	Executor
)

from typify.inferencing.commons import (
    Builtins,
	bind
)
from typify.inferencing.typeutils import TypeUtils

from dataclasses import dataclass

class Inferencer:

	@staticmethod
	def infer(bundle: DependencyBundle):
		mod_meta_map = bundle.mod_meta_map
		meta_lib_map = bundle.meta_lib_map
		sequences = bundle.sequences
		sysmodules = bundle.sysmodules
		libs = bundle.libs
		processed = []
		
		context_map = {
			meta: Context(meta, libs, sysmodules)
			for meta in mod_meta_map.values()
		}
		
		for sequence in sequences:
			for i in range(len(sequence)):
				for meta in sequence:
					lib = meta_lib_map[meta]
					context = context_map[meta]
					symbol = meta.table
					namespace = TypeUtils.instantiate(Builtins.ModuleClass)
					executor = Executor(context, symbol, namespace, meta.tree, [])
					sysmodules[meta.table.fqn] = namespace
					executor.execute()
					bind(lib, namespace, symbol)
					print(Builtins.ModuleClass.type if Builtins.ModuleClass else "No ModuleClass bound")
					processed.append(meta)
		for instance in sysmodules.values():
			print(f"Module: {instance.key}")
		print("\nSequence Followed:")
		joined = " -> ".join(f"{meta}" for meta in processed)
		print(joined)

		