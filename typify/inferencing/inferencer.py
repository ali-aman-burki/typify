from typify.preprocessing.dependency_utils import DependencyBundle
from typify.inferencing.typeutils import (
    TypeUtils, 
    TypeExpr
)
from typify.inferencing.commons import Builtins
from typify.inferencing.executor import (
    Context,
	Executor
)

class Inferencer:

	@staticmethod
	def infer(bundle: DependencyBundle):
		mod_meta_map = bundle.mod_meta_map
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
					sysmodules.setdefault(
						meta.table.fqn, 
						TypeUtils.instantiate(Builtins.get_type("module"))
					)

					Executor(
						context=context_map[meta], 
						symbol=meta.table, 
						namespace=sysmodules[meta.table.fqn], 
						tree=meta.tree,
						snapshot_log=[]
					).execute()
					
					TypeUtils.update_type_expr(
						sysmodules[meta.table.fqn], 
						TypeExpr(Builtins.get_type("module"))
					)
					processed.append(meta)

		print("\nSequence Followed:")
		joined = " -> ".join(f"{meta}" for meta in processed)
		print(joined)

		