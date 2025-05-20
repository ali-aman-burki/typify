from src.builtins_ctn import builtins
from src.symbol_table import Table, VariableTable
from src.contanier_types import *
from src.typeutils import TypeUtils
from src.chain import Chain, Segment
import ast

class Context:
	def __init__(self, library_table: Table, module_table: Table, current_table: Table):
		self.library_table = library_table
		self.module_table = module_table
		self.current_table = current_table

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

	def resolve_start_symbol(self, start_segment: Segment):
		start_id = ast.unparse(start_segment.anchor)
		points_to = []

		if isinstance(start_segment.trail[-1], ast.Call):
			solved_class = self.climb_lookup(start_id, ["classes"])
			if solved_class: points_to.append(solved_class.create_instance())
		
		return points_to

	def resolve(self, node: ast.AST):
		chain = Chain(node)
		points_to = self.resolve_start_symbol(chain.segments[0])
		return points_to
		
	def resolve_type(self, node: ast.AST):
		if isinstance(node, ast.Constant):
			c = builtins.classes[type(node.value).__name__]
			return (Type(c), [c.create_instance()])
		elif isinstance(node, ast.JoinedStr):
			s = builtins.classes["str"]
			return (Type(s), [s.create_instance()])
		elif isinstance(node, ast.BoolOp):
			b = builtins.classes["bool"]
			return (Type(b), [b.create_instance])
		elif isinstance(node, ast.List):
			element_types = [self.resolve_type(el)[0] for el in node.elts]
			l = builtins.classes["list"]
			return (ListType(TypeUtils.unify(element_types)), [l.create_instance()])
		elif isinstance(node, ast.Set):
			element_types = [self.resolve_type(el)[0] for el in node.elts]
			s = builtins.classes["set"]
			return (SetType(TypeUtils.unify(element_types)), [s.create_instance()])
		elif isinstance(node, ast.Tuple):
			element_types = [self.resolve_type(el)[0] for el in node.elts]
			t = builtins.classes["tuple"]
			return (TupleType(element_types), [t.create_instance()])
		elif isinstance(node, ast.Dict):
			key_type = TypeUtils.unify([self.resolve_type(k)[0] for k in node.keys if k is not None])
			value_type = TypeUtils.unify([self.resolve_type(v)[0] for v in node.values if v is not None])
			d = builtins.classes["dict"]
			return (DictType(key_type, value_type), [d.create_instance()])
		else:
			points_to = self.resolve(node)
			types = [Type(pt.class_pointer) for pt in points_to]
			inf_type = TypeUtils.unify(types) if types else UnresolvedType(node) 
			return [inf_type, points_to]