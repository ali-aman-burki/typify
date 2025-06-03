import ast

class Segment:
	def __init__(self, anchor: ast.AST, trail: list[ast.AST]):
		self.anchor = anchor
		self.trail = trail

	def __str__(self):
		def node_str(n):
			if isinstance(n, ast.Name):
				return n.id
			elif isinstance(n, ast.Attribute):
				return f"{n.attr}"
			elif isinstance(n, ast.Call):
				args = [ast.unparse(arg) for arg in n.args]
				kwargs = [f"{kw.arg}={ast.unparse(kw.value)}" for kw in n.keywords]
				all_args = args + kwargs
				return f"({', '.join(all_args)})"
			elif isinstance(n, ast.Subscript):
				try:
					return f"[{ast.unparse(n.slice)}]"
				except Exception:
					return "[?]"
			else:
				return f"({ast.unparse(n)})"

		return "".join(node_str(n) for n in self.trail)


class Chain:
	def __init__(self, node: ast.AST):
		self.segments: list[Segment] = self.build_chain(node)

	def __str__(self):
		parts = []
		for segment in self.segments:
			segment_str = str(segment)
			parts.append(f"{segment_str}")
		
		return " ➜ ".join(parts)

	def build_chain(self, node: ast.AST) -> list[Segment]:
		raw_chain = []

		while True:
			if isinstance(node, ast.Attribute):
				raw_chain.append(node)
				node = node.value
			elif isinstance(node, ast.Call):
				raw_chain.append(node)
				node = node.func
			elif isinstance(node, ast.Subscript):
				raw_chain.append(node)
				node = node.value
			else:
				raw_chain.append(node)
				break

		raw_chain = list(reversed(raw_chain))

		attribute_indices = []
		for i, n in enumerate(raw_chain):
			if isinstance(n, (ast.Name, ast.Attribute, ast.Subscript)) or i == 0:
				attribute_indices.append(i)
				

		processed_chain = []
		for i, current_index in enumerate(attribute_indices):
			next_index = attribute_indices[i + 1] if i + 1 < len(attribute_indices) else len(raw_chain)
			anchor = raw_chain[current_index]
			trail = raw_chain[current_index:next_index]
			processed_chain.append(Segment(anchor, trail))

		return processed_chain