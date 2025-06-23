from typify.preprocessing.dependency_utils import DependencyBundle
from typify.inferencing.analyzer import Analyzer

class Inferencer:

	@staticmethod
	def infer(bundle: DependencyBundle):
		meta_map = bundle.meta_map
		sequences = bundle.sequences
		sysmodules = bundle.sysmodules
		libs = bundle.libs
		processed_modules = []
		
		analysis_map = {
			meta: Analyzer(meta, sysmodules, libs, meta.table)
			for meta in meta_map.values()
		}
		
		for sequence in sequences:
			for meta in sequence:
				analysis_map[meta].process()
				processed_modules.append(meta.table)
		
		print("\nSequence Followed:")
		joined = " -> ".join(f"{module}" for module in processed_modules)
		print(joined)