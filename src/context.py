from src.preloading.commons import builtins_m
from src.symbol_table import Table, VariableTable, ClassTable, FunctionTable
from src.typeutils import TypeUtils
from src.chain import Chain, Segment
import ast

class Context:
	def __init__(self, library_table: Table, module_table: Table, current_table: Table):
		self.library_table = library_table
		self.module_table = module_table
		self.current_table = current_table

	def count_calls(self, node: ast.AST):
		count = 0
		current = node
		while isinstance(current, ast.Call):
			count += 1
			current = current.func
		return count

	def call(self, callable_def: Table) -> set[Table]:
		parent = callable_def.get_enclosing_table()
		if isinstance(parent, ClassTable): 
			return {TypeUtils.create_instance(callable_def, [])}
		elif isinstance(parent, FunctionTable):
			return callable_def.points_to
		return set()

	def lookup(self, identifier: str, defTable: Table, where: list[str]):
		mapping = {
			"variables": defTable.variables,
			"functions": defTable.functions,
			"classes": defTable.classes,
		}
		for key in where:
			dictionary = mapping.get(key)
			if dictionary and identifier in dictionary:
				return dictionary[identifier]

		return None

	def climb_lookup(self, identifier: str, where: list[str]):
		current = self.current_table
		while current:
			defTable = current.get_latest_definition()
			resolved = self.lookup(identifier, defTable, where)
			if resolved: return resolved																																																								
			current = current.get_enclosing_table()

	def verify_lhs(self, node: ast.AST):
		if isinstance(node, ast.Name):
			name = node.id
			if name not in self.current_table.get_latest_definition().variables:
				self.current_table.get_latest_definition().add_variable(VariableTable(name))
			return self.current_table.get_latest_definition().variables[name]
		return None

	def resolve_start(self, start_segment: Segment) -> set[Table]:
		starting_identifier = ast.unparse(start_segment.anchor)
		found = self.climb_lookup(starting_identifier, ["variables"])
		if found:
			fd = found.get_latest_definition()

			if isinstance(start_segment.trail[-1], ast.Name):
				return (fd.type, fd.points_to)

			elif isinstance(start_segment.trail[-1], ast.Call):
				points_to = fd.points_to
				numcalls = self.count_calls(start_segment.trail[-1])

				for _ in range(numcalls):
					results = []
					for instance in points_to:
						origin = instance.origin
						result = self.call(origin)
						results.append(result)

					points_to = {pt for _, pts in results for pt in pts}

				return points_to

		return set()

	def resolve(self, node: ast.AST) -> set[Table]:
		chain = Chain(node)
		return self.resolve_start(chain.segments[0])
		
	def resolve_type(self, node: ast.AST) -> set[Table]:
		if isinstance(node, ast.Constant):
			c = builtins_m.classes[type(node.value).__name__]
			cinstance = TypeUtils.create_instance(c, [])
			return {cinstance}
		
		elif isinstance(node, ast.JoinedStr):
			s = builtins_m.classes["str"]
			sinstance = TypeUtils.create_instance(s, [])
			return {sinstance}
		
		elif isinstance(node, ast.BoolOp):
			b = builtins_m.classes["bool"]
			binstance = b.create_instance(b)
			return {binstance}
		
		elif isinstance(node, ast.List):
			l = builtins_m.classes["list"]
			linstance = TypeUtils.create_instance(l, [])
			return {linstance}
		
		elif isinstance(node, ast.Set):
			s = builtins_m.classes["set"]
			sinstance = TypeUtils.create_instance(s, [])
			return {sinstance}
		
		elif isinstance(node, ast.Tuple):
			t = builtins_m.classes["tuple"]
			tinstance = TypeUtils.create_instance(t, [])
			return {tinstance}
		
		elif isinstance(node, ast.Dict):
			d = builtins_m.classes["dict"]
			dinstance = TypeUtils.create_instance(d, [])
			return {dinstance}
		
		elif isinstance(node, ast.BinOp):
			return self.resolve_type(node.left)
		
		else:
			return self.resolve(node)
