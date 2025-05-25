from src.builtins_ctn import builtins
from src.symbol_table import Table, VariableTable, ClassTable, FunctionTable
from src.contanier_types import *
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

	def call(self, callable_def: Table):
		parent = callable_def.get_enclosing_table()
		if isinstance(parent, ClassTable): return (Type(parent), [parent.create_instance(callable_def)])
		elif isinstance(parent, FunctionTable): 
			return (callable_def.type, callable_def.points_to)
		return (UnresolvedType(None), [])

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

	def resolve_start(self, start_segment: Segment) -> tuple[Type, list[Table]]:
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
					results = [self.call(tdef) for instance in points_to for tdef in instance.returns]
					types = [res[0] for res in results]
					points_to = [pt for res in results for pt in res[1]]

				inferred_type = TypeUtils.unify(types)
				return (inferred_type, points_to)

		return (UnresolvedType(None), [])


	def resolve(self, node: ast.AST) -> tuple[Type, list[Table]]:
		chain = Chain(node)
		return self.resolve_start(chain.segments[0])
		
	def resolve_type(self, node: ast.AST) -> tuple[Type, list[Table]]:
		if isinstance(node, ast.Constant):
			c = builtins.classes[type(node.value).__name__]
			return (Type(c), [c])
		elif isinstance(node, ast.JoinedStr):
			s = builtins.classes["str"]
			return (Type(s), [s])
		elif isinstance(node, ast.BoolOp):
			b = builtins.classes["bool"]
			return (Type(b), [b])
		elif isinstance(node, ast.List):
			element_types = [self.resolve_type(el)[0] for el in node.elts]
			l = builtins.classes["list"]
			inf_type = ListType(TypeUtils.unify(element_types))
			linstance = l.create_instance(l)
			return (inf_type, [linstance])
		elif isinstance(node, ast.Set):
			element_types = [self.resolve_type(el)[0] for el in node.elts]
			inf_type = SetType(TypeUtils.unify(element_types))
			s = builtins.classes["set"]
			sinstance = s.create_instance(s)
			return (inf_type, [sinstance])
		elif isinstance(node, ast.Tuple):
			element_types = [self.resolve_type(el)[0] for el in node.elts]
			inf_type = TupleType(element_types)
			t = builtins.classes["tuple"]
			tinstance = t.create_instance(t)
			return (inf_type, [tinstance])
		elif isinstance(node, ast.Dict):
			key_type = TypeUtils.unify([self.resolve_type(k)[0] for k in node.keys if k is not None])
			value_type = TypeUtils.unify([self.resolve_type(v)[0] for v in node.values if v is not None])
			d = builtins.classes["dict"]
			inf_type = DictType(key_type, value_type)
			dinstance = d.create_instance(d)
			return (inf_type, [dinstance])
		else:
			resolved = self.resolve(node)
			return resolved