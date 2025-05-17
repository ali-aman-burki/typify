import ast
from dataclasses import dataclass
from typing import List

@dataclass
class Segment:
	anchor: ast.AST
	trail: List[ast.AST]

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
				return ast.dump(n)

		return "".join(node_str(n) for n in self.trail)


class Chain:
	def __init__(self, node: ast.AST):
		self.segments: list[Segment] = self.build_chain(node)

	def __str__(self):
		return " ➜ ".join(str(segment) for segment in self.segments)

	def build_chain(self, node: ast.AST) -> List[Segment]:
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
			elif isinstance(node, ast.Name):
				raw_chain.append(node)
				break
			else:
				raw_chain.append(node)
				break

		raw_chain = list(reversed(raw_chain))

		attribute_indices = [
			i for i, n in enumerate(raw_chain)
			if isinstance(n, (ast.Name, ast.Attribute))
		]

		processed_chain = []
		for i, current_index in enumerate(attribute_indices):
			next_index = attribute_indices[i + 1] if i + 1 < len(attribute_indices) else len(raw_chain)
			anchor = raw_chain[current_index]
			trail = raw_chain[current_index:next_index]
			processed_chain.append(Segment(anchor=anchor, trail=trail))

		return processed_chain
