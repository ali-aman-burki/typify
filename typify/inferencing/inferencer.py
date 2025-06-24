from typify.preprocessing.dependency_utils import DependencyBundle
from typify.inferencing.executer import (
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
		processed_modules = []
		

		context_map = {
			meta: Context(meta, libs, sysmodules)
			for meta in mod_meta_map.values()
		}
		
		for sequence in sequences:
			for meta in sequence:
				lib = meta_lib_map[meta]
				context = context_map[meta]
				symbol = meta.table
				namespace = TypeUtils.instantiate(Builtins.ModuleClass)
				bind(lib, namespace, symbol)
				executor = Executor(context, symbol, namespace, meta.tree)
				executor.execute()
				processed_modules.append(meta.table)
		
		print("\nSequence Followed:")
		joined = " -> ".join(f"{module}" for module in processed_modules)
		print(joined)