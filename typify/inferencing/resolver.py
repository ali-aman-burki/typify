
import ast

from typify.preprocessing.module_meta import ModuleMeta
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.call_stack import CallStack
from typify.inferencing.unpacking_utils import (
	TargetEntry,
	PackGroup
)
from typify.preprocessing.symbol_table import (
	ReferenceSet,
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

	def attribute_lookup(
			self, 
			instance: InstanceTable, 
			attr: str
		) -> NameTable:
		
		if attr in instance.names: return instance.names[attr]
		
		if instance.type_expr.typedef == Builtins.get_type("type"):
			for m in instance.origin.mro:
				if attr in m.names: return m.names[attr]
		else:
			for m in instance.type_expr.typedef.mro:
				if attr in m.names: return m.names[attr]
		
		return None

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
	def resolve_value(self, node: ast.Expr) -> ReferenceSet:
		from typify.inferencing.call_dispatcher import CallDispatcher
		
		if isinstance(node, ast.Constant):
			type_name = type(node.value).__name__
			instance = ConstantObjects.get(type_name)
			return ReferenceSet(instance)
		
		elif isinstance(node, ast.JoinedStr):
			typeclass = Builtins.get_type("str")
			instance = TypeUtils.instantiate(typeclass)
			return ReferenceSet(instance)
		
		elif isinstance(node, ast.List):
			typeclass = Builtins.get_type("list")
			typeargs = []
			for elt in node.elts:
				resolved = self.resolve_value(elt)
				unified = TypeUtils.unify(resolved)
				typeargs.append(unified)
			instance = TypeUtils.instantiate(typeclass, [TypeUtils.unify_from_exprs(typeargs)])
			return ReferenceSet(instance)
		
		elif isinstance(node, ast.Set):
			typeclass = Builtins.get_type("set")
			typeargs = []
			for elt in node.elts:
				resolved = self.resolve_value(elt)
				unified = TypeUtils.unify(resolved)
				typeargs.append(unified)
			instance = TypeUtils.instantiate(typeclass, [TypeUtils.unify_from_exprs(typeargs)])
			return ReferenceSet(instance)
		
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
			return ReferenceSet(instance)
		
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
			return ReferenceSet(instance)
		
		elif isinstance(node, ast.Call):
			dispatcher = CallDispatcher(self, node)
			return dispatcher.dispatch()

		elif isinstance(node, ast.Name):
			name = self.LEGB_lookup(node.id)
			if name: return name.get_latest_definition().refset
			return ReferenceSet(TypeUtils.instantiate(Typing.get_type("Any")))
		
		elif isinstance(node, ast.Attribute):
			value_references = self.resolve_value(node.value)
			result = ReferenceSet()
			for ref in value_references:
				namet = self.attribute_lookup(ref, node.attr)
				if namet:
					namedef = namet.get_latest_definition()
					result.update(namedef.refset)
			return result if result else ReferenceSet(TypeUtils.instantiate(Typing.get_type("Any")))
		else:
			return ReferenceSet(TypeUtils.instantiate(Typing.get_type("Any")))
	
	#TODO: in the future, remove hardcoded logic for tuple and generalize it based on generics
	#TODO: add support for starred unpacking
	def process_assignment(
			self, 
			resolved_target: PackGroup, 
			resolved_value: ReferenceSet
		):
		targets: set[TargetEntry] = set()
		for ref in resolved_value:
			for i in range(len(resolved_target.groups)):
				group = resolved_target.groups[i]
				if isinstance(group, PackGroup):
					next_instances = TypeUtils.instantiate_from_type_expr(ref.type_expr.typeargs[0])
					if ref.type_expr.typedef == Builtins.get_type("tuple"):
						if len(ref.store) > i:
							next_instances = ref.store[i]
						elif len(ref.type_expr.typeargs) > i:
							next_instances = TypeUtils.instantiate_from_type_expr(ref.type_expr.typeargs[i])
					self.process_assignment(group, next_instances)
				else:
					for target_entry in group:
						target_entry.definition.refset.add(ref)
						targets.add(target_entry)
		
		for target in targets:
			target.namespace_name.new_def(target.definition)
			if target.symbol_name:
				ndef = DefinitionTable((target.definition.module, target.definition.position))
				ndef.refset.update(target.definition.refset)
				target.symbol_name.merge_def(ndef)	
