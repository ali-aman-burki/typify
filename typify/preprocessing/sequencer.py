from collections import defaultdict

from typify.preprocessing.module_meta import ModuleMeta

class Sequencer:

	@staticmethod
	def _tarjan(graph: dict[ModuleMeta, list[ModuleMeta]]):
		index = 0
		indices: dict[ModuleMeta, int] = {}
		low_links: dict[ModuleMeta, int] = {}
		on_stack: set[ModuleMeta] = set()
		stack: list[ModuleMeta] = []
		result: list[list[ModuleMeta]] = []

		def strongconnect(node: ModuleMeta):
			nonlocal index
			indices[node] = index
			low_links[node] = index
			index += 1
			stack.append(node)
			on_stack.add(node)

			for neighbor in graph.get(node, []):
				if neighbor not in indices:
					strongconnect(neighbor)
					low_links[node] = min(low_links[node], low_links[neighbor])
				elif neighbor in on_stack:
					low_links[node] = min(low_links[node], indices[neighbor])

			if low_links[node] == indices[node]:
				scc: list[ModuleMeta] = []
				while True:
					popped_node = stack.pop()
					on_stack.remove(popped_node)
					scc.append(popped_node)
					if popped_node == node:
						break
				result.append(scc)

		for node in graph:
			if node not in indices:
				strongconnect(node)

		return result

	@staticmethod
	def _build_condensed_graph(
		graph: dict[ModuleMeta, list[ModuleMeta]],
		sccs: list[list[ModuleMeta]]
	) -> dict[tuple[ModuleMeta, ...], set[tuple[ModuleMeta, ...]]]:
		condensed: dict[tuple[ModuleMeta, ...], set[tuple[ModuleMeta, ...]]] = {
			tuple(scc): set() for scc in sccs
		}

		module_to_scc: dict[ModuleMeta, tuple[ModuleMeta, ...]] = {}
		for scc in condensed.keys():
			for mod in scc:
				module_to_scc[mod] = scc

		for src, targets in graph.items():
			src_scc = module_to_scc[src]
			for tgt in targets:
				tgt_scc = module_to_scc[tgt]
				if src_scc is not tgt_scc:
					condensed[tgt_scc].add(src_scc)

		def reachable(start: tuple[ModuleMeta, ...],
					  goal: tuple[ModuleMeta, ...],
					  visited: set[tuple[ModuleMeta, ...]] | None = None) -> bool:
			if visited is None:
				visited = set()
			if start == goal:
				return True
			for nxt in condensed[start]:
				if nxt not in visited:
					visited.add(nxt)
					if reachable(nxt, goal, visited):
						return True
			return False

		for u in list(condensed.keys()):
			to_remove: set[tuple[ModuleMeta, ...]] = set()
			for v in condensed[u]:
				for w in condensed[u]:
					if w != v and reachable(w, v):
						to_remove.add(v)
						break
			condensed[u] -= to_remove

		return condensed

	@staticmethod
	def _find_roots(condensed: dict[tuple, set[tuple]]) -> list[tuple]:
		all_nodes = set(condensed.keys())
		pointed_to = {v for tgts in condensed.values() for v in tgts}
		roots = list(all_nodes - pointed_to)
		return roots

	@staticmethod
	def generate_condensed_graph(graph: dict[ModuleMeta, list[ModuleMeta]]):
		sequences: list[list[ModuleMeta]] = Sequencer._tarjan(graph)

		for seq in sequences:
			seq.reverse()

		condensed = Sequencer._build_condensed_graph(graph, sequences)
		return condensed

	@staticmethod
	def generate_sequences(graph: dict[ModuleMeta, list[ModuleMeta]]) -> list[list[ModuleMeta]]:
		sequences: list[list[ModuleMeta]] = Sequencer._tarjan(graph)

		for seq in sequences:
			seq.reverse()

		return sequences
