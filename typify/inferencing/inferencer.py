from typify.preprocessing.dependency_utils import DependencyBundle
from typify.inferencing.analyzer import Analyzer
from typify.preprocessing.symbol_table import InstanceTable

class Inferencer:

	@staticmethod
	def infer(bundle: DependencyBundle): 
		sequence = bundle.resolving_sequence
		precedence = [meta.table for meta in sequence]
		sysmodules = bundle.sysmodules
		libs = bundle.libs
		for meta in sequence:
			Analyzer(meta, precedence, sysmodules, libs).visit(meta.tree)