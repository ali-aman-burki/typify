class Sequencer:

	@staticmethod
	def _tarjan(graph: dict[str, list[str]]):
		index = 0
		indices: dict[str, int] = {}
		low_links: dict[str, int] = {}
		on_stack: set[str] = set()
		stack: list[str] = []
		result: list[list[str]] = []

		def strongconnect(node: str):
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
				scc: list[str] = []
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
	def build_condensed_graph(graph, sccs):
		condensed = {tuple(scc): set() for scc in sccs}
		module_to_scc = {}
		for scc in condensed.keys():
			for mod in scc:
				module_to_scc[mod] = scc

		# raw edges (reversed orientation)
		for src, targets in graph.items():
			src_scc = module_to_scc[src]
			for tgt in targets:
				tgt_scc = module_to_scc[tgt]
				if src_scc is not tgt_scc:
					condensed[tgt_scc].add(src_scc)

		# prune transitive edges
		def reachable(start, goal, visited=None):
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
			to_remove = set()
			for v in condensed[u]:
				# check if v is also reachable via some other neighbor of u
				for w in condensed[u]:
					if w != v and reachable(w, v):
						to_remove.add(v)
						break
			condensed[u] -= to_remove

		return condensed


	@staticmethod
	def generate_sequences(graph: dict[str, list[str]]) -> list[list[str]]:
		sequences: list[list[str]] = Sequencer._tarjan(graph)

		for seq in sequences:
			seq.reverse()

		return sequences

def find_roots(condensed: dict[tuple, set[tuple]]) -> list[tuple]:
	all_nodes = set(condensed.keys())
	pointed_to = {v for tgts in condensed.values() for v in tgts}
	roots = list(all_nodes - pointed_to)
	return roots

def test_sequencer():
	graph = {
		"d": ["a"],
		"e": ["a", "d"],
		"f": ["a"],
		"a": ["b"],
		"b": ["c"],
		"c": ["a"]
	}

	# Step 1: find SCCs
	sccs = Sequencer.generate_sequences(graph)
	print("SCCs:", sccs)

	# Step 2: build condensation DAG
	condensed = Sequencer.build_condensed_graph(graph, sccs)
	print("Condensed graph:")
	for src, tgts in condensed.items():
		print(f"  {src} -> {tgts}")
	
	#roots:
	roots = find_roots(condensed)
	print("Roots of the condensed graph:", roots)

if __name__ == "__main__":
	test_sequencer()
