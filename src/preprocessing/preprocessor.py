from pathlib import Path

from src.preprocessing.graph_utils import GraphUtils

class Preprocessor:

	def generate_resolving_sequence(self):
		# for k, v in self.dependency_graph.items():
		# 	joined = ",".join(repr(repr(m)) for m in v)
		# 	print(f"{k} -> [{joined}]")

		sccs = GraphUtils.tarjan(self.dependency_graph)
		resolving_sequence = GraphUtils.generate_resolving_sequence(sccs)
		# joined = "\n".join([repr(m) for m in resolving_sequence])
		# print("\nsequence:")
		# print(joined)
		return resolving_sequence