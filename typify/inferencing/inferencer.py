from typify.preprocessing.dependency_utils import DependencyBundle
from typify.inferencing.analyzer import Analyzer
from typify.preprocessing.symbol_table import InstanceTable

class Inferencer:

	@staticmethod
	def infer(bundle: DependencyBundle):
		meta_map = bundle.meta_map
		sequence = bundle.resolving_sequence
		precedence = [meta.table for meta in sequence]
		sysmodules = bundle.sysmodules
		libs = bundle.libs

		analysis_map = {
			meta: Analyzer(meta, precedence, sysmodules, libs)
			for meta in meta_map.values()
		}
		
		for meta in sequence: analysis_map[meta].process()