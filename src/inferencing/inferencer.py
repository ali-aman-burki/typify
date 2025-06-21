from src.preprocessing.dependency_utils import DependencyBundle
from src.inferencing.analyzer import Analyzer

class Inferencer:

	@staticmethod
	def infer(bundle: DependencyBundle): 
		sequence = bundle.resolving_sequence
		precedence = [meta.table for meta in sequence]
		module_object_map = bundle.module_object_map
		libs = bundle.libs
		for meta in sequence: Analyzer(meta, precedence, module_object_map, libs).visit(meta.tree)