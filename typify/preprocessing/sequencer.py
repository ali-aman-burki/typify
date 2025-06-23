class Sequencer:
	
	@staticmethod
	def _tarjan(graph):
		index = 0
		indices = {}
		low_links = {}
		on_stack = set()
		stack = []
		result = []

		def strongconnect(node):
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
				scc = []
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
	def generate_sequences(graph):
		sequences = Sequencer._tarjan(graph)
		return sequences
