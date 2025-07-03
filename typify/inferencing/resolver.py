
import ast

from typify.preprocessing.module_meta import ModuleMeta
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.call_stack import CallStack
from typify.inferencing.unpacking_utils import (
	TargetEntry,
	PackGroup
)
from typify.preprocessing.symbol_table import (
	Table,
	NameTable,
	ClassTable,
	PackageTable,
	LibraryTable,
	InstanceTable,
	DefinitionTable,
)
from typify.inferencing.commons import (
	Context,
	Builtins,
	Typing,
	ConstantObjects
)

class Resolver:
	def __init__(
			self, 
			context: Context,
			module_meta: ModuleMeta,
			symbol: Table, 
			namespace: InstanceTable,
			call_stack: CallStack
		):
		self.context = context
		self.module_meta = module_meta
		self.symbol = symbol
		self.namespace = namespace
		self.call_stack = call_stack

	def LEGB_lookup(self, name: str) -> NameTable:
		current_symbol = self.symbol

		while not isinstance(current_symbol, (LibraryTable, PackageTable)):
			if isinstance(current_symbol, ClassTable):
				current_symbol = current_symbol.get_enclosing_table()
				continue
			
			result = self.context.symbol_map[current_symbol.get_latest_definition()].names.get(name)
			if result: return result

			current_symbol = current_symbol.get_enclosing_table()

		return Builtins.module().names.get(name, None)

	def resolve_target(self, expr: ast.expr) -> PackGroup:
		position = (expr.lineno, expr.col_offset)
		defkey = (self.module_meta.table, position)

		if isinstance(expr, ast.Name):
			symbol_name = self.symbol.get_name(expr.id)
			namespace_name = self.namespace.get_name(expr.id)
			entry = TargetEntry(
				definition=DefinitionTable(defkey), 
				namespace_name=namespace_name,
				symbol_name=symbol_name
			)
			return PackGroup(groups=[{entry}], starred=False)

		elif isinstance(expr, (ast.Tuple, ast.List)):
			inner_groups: list[set[TargetEntry] | PackGroup] = []
			for elt in expr.elts:
				subgroup = self.resolve_target(elt)
				inner_groups.append(subgroup)
			return PackGroup(groups=inner_groups, starred=False)

		elif isinstance(expr, ast.Starred):
			resolved = self.resolve_target(expr.value)
			return PackGroup(groups=resolved.groups, starred=True)

		elif isinstance(expr, ast.Attribute):
			instances = self.resolve_value(expr.value)
			group: set[TargetEntry] = set()
			for instance in instances:
				if expr.attr in instance.names:
					entry = TargetEntry(
						definition=DefinitionTable(defkey), 
						namespace_name=instance.names[expr.attr])
					group.add(entry)
				else:
					
					symbol_name = None
					if instance.origin:
						symbol_name = instance.origin.get_name(expr.attr)
					namespace_name = instance.get_name(expr.attr)
					entry = TargetEntry(
						definition=DefinitionTable(defkey), 
						namespace_name=namespace_name,
						symbol_name=symbol_name
					)
					group.add(entry)
			return PackGroup(groups=[group], starred=False)
		else:
			return PackGroup(groups=[], starred=False)

	
	#TODO: need support for literal types i.e Literal[...]
	def resolve_value(self, node: ast.Expr) -> set[InstanceTable]:
		from typify.inferencing.function_utils import FunctionUtils
		
		if isinstance(node, ast.Constant):
			type_name = type(node.value).__name__
			instance = ConstantObjects.get(type_name)
			return {instance}
		
		elif isinstance(node, ast.JoinedStr):
			typeclass = Builtins.get_type("str")
			instance = TypeUtils.instantiate(typeclass)
			return {instance}
		
		elif isinstance(node, ast.List):
			typeclass = Builtins.get_type("list")
			typeargs = []
			for elt in node.elts:
				resolved = self.resolve_value(elt)
				unified = TypeUtils.unify(resolved)
				typeargs.append(unified)
			instance = TypeUtils.instantiate(typeclass, [TypeUtils.unify_from_exprs(typeargs)])
			return {instance}
		
		elif isinstance(node, ast.Set):
			typeclass = Builtins.get_type("set")
			typeargs = []
			for elt in node.elts:
				resolved = self.resolve_value(elt)
				unified = TypeUtils.unify(resolved)
				typeargs.append(unified)
			instance = TypeUtils.instantiate(typeclass, [TypeUtils.unify_from_exprs(typeargs)])
			return {instance}
		
		elif isinstance(node, ast.Tuple):
			typeclass = Builtins.get_type("tuple")
			store = []
			typeargs = []
			for elt in node.elts:
				resolved = self.resolve_value(elt)
				unified = TypeUtils.unify(resolved)
				typeargs.append(unified)
				store.append(resolved)
			instance = TypeUtils.instantiate(typeclass, typeargs)
			instance.store = store
			return {instance}
		
		elif isinstance(node, ast.Dict):
			typeclass = Builtins.get_type("dict")
			keyargs = []
			valueargs = []
			for elt in node.keys:
				resolved = self.resolve_value(elt)
				unified = TypeUtils.unify(resolved)
				keyargs.append(unified)
			for elt in node.values:
				resolved = self.resolve_value(elt)
				unified = TypeUtils.unify(resolved)
				valueargs.append(unified)
			instance = TypeUtils.instantiate(
				typeclass, 
				[TypeUtils.unify_from_exprs(keyargs), TypeUtils.unify_from_exprs(valueargs)]
			)
			return {instance}
		
		elif isinstance(node, ast.Call):
			candidates = self.resolve_value(node.func)
			for candidate in candidates:
				if candidate.type_expr.typedef == Builtins.get_type("function"):
					function_table = candidate.origin
					param_map = function_table.parameters
					argmap = FunctionUtils.map_call_arguments(node, param_map, self)
					return FunctionUtils.run_function(
						self.context, 
						argmap, 
						function_table, 
						self.call_stack
					)
				
			return {TypeUtils.instantiate(Typing.get_type("Any"))}
		
		elif isinstance(node, ast.Name):
			name = self.LEGB_lookup(node.id)
			if name: return name.get_latest_definition().points_to
			return {TypeUtils.instantiate(Typing.get_type("Any"))}
		
		elif isinstance(node, ast.Attribute):
			value_points_tos = self.resolve_value(node.value)
			results = set()
			for pt in value_points_tos:
				if node.attr in pt.names:
					namedef = pt.names[node.attr].get_latest_definition()
					results.update(namedef.points_to)
			return results if results else {TypeUtils.instantiate(Typing.get_type("Any"))}
		else:
			return {TypeUtils.instantiate(Typing.get_type("Any"))}
	
	#TODO: in the future, remove hardcoded logic for tuple and generalize it based on generics
	#TODO: add support for starred unpacking
	def process_assignment(
			self, 
			resolved_target: PackGroup, 
			resolved_value: set[InstanceTable]
		):
		targets: set[TargetEntry] = set()
		for pt in resolved_value:
			for i in range(len(resolved_target.groups)):
				group = resolved_target.groups[i]
				if isinstance(group, PackGroup):
					next_instances = TypeUtils.instantiate_from_type_expr(pt.type_expr.typeargs[0])
					if pt.type_expr.typedef == Builtins.get_type("tuple"):
						if len(pt.store) > i:
							next_instances = pt.store[i]
						elif len(pt.type_expr.typeargs) > i:
							next_instances = TypeUtils.instantiate_from_type_expr(pt.type_expr.typeargs[i])
					self.process_assignment(group, next_instances)
				else:
					for target_entry in group:
						target_entry.definition.points_to.add(pt)
						targets.add(target_entry)
		
		for target in targets:
			target.namespace_name.new_def(target.definition)
			if target.symbol_name:
				ndef = DefinitionTable((target.definition.module, target.definition.position))
				ndef.points_to.update(target.definition.points_to)
				target.symbol_name.merge_def(ndef)	
