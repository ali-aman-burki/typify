import ast
import copy
from collections import defaultdict

from typify.preprocessing.module_meta import ModuleMeta
from typify.inferencing.function_utils import FunctionUtils
from typify.preprocessing.dependency_utils import DependencyUtils
from typify.inferencing.mro import MROBuilder
from typify.inferencing.resolver import Resolver
from typify.inferencing.typeutils import (
    TypeUtils, 
    TypeExpr
)
from typify.inferencing.commons import (
	Context,
	Builtins,
	Typing,
	ConstantObjects,
	ArgTuple
)
from typify.preprocessing.symbol_table import (
	ReferenceSet,
	InstanceTable,
	DefinitionTable,
	Table,
	CallFrameTable
)

class Executor(ast.NodeVisitor):
	def __init__(
			self, 
			context: Context,
			module_meta: ModuleMeta,
			symbol: Table,
			namespace: InstanceTable, 
			arguments: dict[str, ArgTuple],
			call_stack: list,
			tree: ast.AST,
			snapshot_log: list[ReferenceSet] = None
		):
		self.context = context
		self.module_meta = module_meta
		self.symbol = symbol
		self.namespace = namespace
		self.call_stack = call_stack
		self.tree = tree
		self.snapshot_log = snapshot_log if snapshot_log else []
		self.returns = ReferenceSet()

		self.resolver = Resolver(
			self.context, 
			self.module_meta, 
			self.symbol, 
			self.namespace,
			self.call_stack
		)

		for argname in arguments:
			argtuple = arguments[argname]
			refset = argtuple.refset
			defkey = argtuple.defkey

			namespace_name = self.namespace.get_name(argname)
			symbol_name = self.symbol.get_name(argname)

			ndef = DefinitionTable(defkey)
			ndef.refset.update(refset)

			namespace_name.new_def(ndef)
			merged = symbol_name.merge_def(ndef)

			position = (self.symbol.tree.lineno, self.symbol.tree.col_offset)
			self.module_meta.fslots[position][1][argname] = merged.refset.as_type()

	def execute(self) -> ReferenceSet: 
		self.visit(self.tree)
		if isinstance(self.namespace, CallFrameTable):
			if not TypeUtils.has_complete_return(self.tree.body):
				self.returns.add(ConstantObjects.get("NoneType"))
				self.symbol.refset.add(ConstantObjects.get("NoneType"))

				position = (self.symbol.tree.lineno, self.symbol.tree.col_offset)
				self.module_meta.fslots[position][2] = self.symbol.refset
		return self.returns

	def snapshot(self): 
		result = []
		for references in self.snapshot_log:
			counter = defaultdict(int)
			labeled = set()
			for ref in references:
				counter[ref.label()] += 1
				label = f"{ref.label()}#{counter[ref.label()]}"
				labeled.add(label)
			result.append(labeled)
		return result

	def add_to_snapshot(self, refset: ReferenceSet):
		self.snapshot_log.append(refset.copy())

	def visit_Return(self, node):
		resolved = self.resolver.resolve_value(node.value)
		if not node.value:
			resolved = ReferenceSet(ConstantObjects.get("NoneType"))

		self.add_to_snapshot(resolved)

		self.symbol.refset.update(resolved)
		self.returns.update(resolved)

		position = (self.symbol.tree.lineno, self.symbol.tree.col_offset)
		self.module_meta.fslots[position][2] = self.symbol.refset

	def visit_Import(self, node):
		position = (node.lineno, node.col_offset)
		defkey = (self.module_meta.table, position)
		for alias in node.names:
			name = alias.asname if alias.asname else alias.name.split(".")[0]
			self.symbol.get_name(name).merge_def(DefinitionTable(defkey))
			self.namespace.get_name(name).new_def(DefinitionTable(defkey))

			object_chain = DependencyUtils.resolve_module_objects(
				defkey, 
				self.context.libs, 
				self.context.sysmodules, 
				alias.name
			)
			if not object_chain:
				deftable = DefinitionTable(defkey)
				deftable.refset.add(TypeUtils.instantiate(Typing.get_type("Any")))
				self.symbol.get_name(name).merge_def(deftable)
				self.namespace.get_name(name).merge_def(deftable)
				continue
			
			deftable = DefinitionTable(defkey)
			deftable.refset.add(object_chain[-1] if alias.asname else object_chain[0])
			self.symbol.get_name(name).merge_def(deftable)
			self.namespace.get_name(name).merge_def(deftable)

			reference = self.namespace.get_name(name).lookup_definition(defkey).refset
			self.add_to_snapshot(reference)

		self.generic_visit(node)
	
	def visit_ImportFrom(self, node):
		position = (node.lineno, node.col_offset)
		defkey = (self.module_meta.table, position)
		object_chain = DependencyUtils.resolve_module_objects(
			defkey,
			self.context.libs,
			self.context.sysmodules,
			node.module, node.level
		)
		
		if node.names[0].name == "*":
			if not object_chain: return
			for name in object_chain[-1].names.values():
				lat_def = name.get_latest_definition()
				self.namespace.get_name(name.key).new_def(lat_def)
				self.add_to_snapshot(lat_def.refset)
		else:
			for alias in node.names:
				name = alias.asname if alias.asname else alias.name
				self.symbol.get_name(name).merge_def(DefinitionTable(defkey))
				self.namespace.get_name(name).new_def(DefinitionTable(defkey))
				
				if not object_chain: 
					deftable = DefinitionTable(defkey)
					deftable.refset.add(TypeUtils.instantiate(Typing.get_type("Any")))
					self.symbol.get_name(name).merge_def(deftable)
					self.namespace.get_name(name).merge_def(deftable)
					return
				
				if alias.name in object_chain[-1].names:
					mname = object_chain[-1].names[alias.name]
					lat_def = mname.get_latest_definition()

					deftable = DefinitionTable(defkey)
					deftable.refset.update(lat_def.refset)
					self.symbol.get_name(name).merge_def(deftable)
					self.namespace.get_name(name).merge_def(deftable)
				else:
					fqn = DependencyUtils.to_absolute_name(
						self.module_meta.table, 
						node.module, 
						node.level
					)
					fqn += f".{alias.name}"
					new_object_chain = DependencyUtils.resolve_module_objects(
						defkey,
						self.context.libs,
						self.context.sysmodules,
						fqn
					)
					if not new_object_chain: return

					deftable = DefinitionTable(defkey)
					deftable.refset.add(new_object_chain[-1])
					self.symbol.get_name(name).merge_def(deftable)
					self.namespace.get_name(name).merge_def(deftable)
				
				reference = self.namespace.get_name(name).lookup_definition(defkey).refset
				self.add_to_snapshot(reference)
				
		self.generic_visit(node)

	#TODO: add support for multiple possible candidates for a single base
	def visit_ClassDef(self, class_tree: ast.ClassDef):
		name = class_tree.name
		position = (class_tree.lineno, class_tree.col_offset)
		defkey = (self.module_meta.table, position)

		class_table = self.symbol.get_class(name)
		entering_symbol = class_table.merge_def(DefinitionTable(defkey))

		builtins_module_object = self.context.symbol_map.get(Builtins.module())
		entering_symbol.bases.clear()

		if not class_tree.bases:
			if builtins_module_object:
				object_class = builtins_module_object.names.get("object")
				if object_class:
					object_def = object_class.get_latest_definition()
					instance = object_def.refset.ref()
					entering_symbol.bases.append(instance)
					self.add_to_snapshot({instance})

		for base in class_tree.bases:
			base_inst = self.resolver.resolve_value(base).ref()
			if base_inst.type_expr.typedef != Typing.get_type("Any"):
				entering_symbol.bases.append(base_inst)
				self.add_to_snapshot({base_inst})

		entering_namespace = self.context.symbol_map.setdefault(
			entering_symbol,
			TypeUtils.instantiate(
				Builtins.get_type("type"),
				[TypeExpr(entering_symbol)]
			)
		)
		entering_namespace.type_expr = TypeExpr(
			Builtins.get_type("type"), 
			[TypeExpr(entering_symbol)]
		)

		entering_namespace.origin = entering_symbol
		Executor(
			context=self.context,
			module_meta=self.module_meta,
			symbol=entering_symbol,
			namespace=entering_namespace,
			arguments={},
			call_stack=self.call_stack,
			tree=ast.Module(class_tree.body, type_ignores=[]),
			snapshot_log=self.snapshot_log
		).execute()

		deftable = DefinitionTable(defkey)
		deftable.refset.add(entering_namespace)
		self.symbol.get_name(name).merge_def(deftable)
		self.namespace.get_name(name).new_def(deftable)

		entering_symbol.mro = MROBuilder.build_mro(entering_namespace)

		self.add_to_snapshot(deftable.refset)
		
	def visit_FunctionDef(self, func_tree: ast.FunctionDef | ast.AsyncFunctionDef):
		position = (func_tree.lineno, func_tree.col_offset)
		defkey = (self.module_meta.table, position)
		name = func_tree.name

		deftable = DefinitionTable(defkey)
		self.symbol.get_name(name).merge_def(deftable)
		self.namespace.get_name(name).new_def(deftable)

		function_table = self.symbol.get_function(name)
		function_def = function_table.merge_def(DefinitionTable(defkey))
		function_def.tree = func_tree
		function_def.parameters = FunctionUtils.collect_parameters(func_tree, self.resolver)

		for k, v in function_def.parameters.items():
			ndef = DefinitionTable(v.defkey)
			ndef.refset = v.refset
			mdef = function_def.get_name(k).merge_def(ndef)
			self.module_meta.fslots[position][1][k] = mdef.refset.as_type()

		func_obj = self.context.symbol_map.setdefault(
			function_def,
			TypeUtils.instantiate(Builtins.get_type("function"))
		)
		func_obj.type_expr.typedef = Builtins.get_type("function")
		func_obj.origin = function_def

		deftable = DefinitionTable(defkey)
		deftable.refset.add(func_obj)
		self.symbol.get_name(name).merge_def(deftable)
		self.namespace.get_name(name).merge_def(deftable)

		self.add_to_snapshot(deftable.refset)
	
	def visit_AsyncFunctionDef(self, node):
		self.visit_FunctionDef(node)

	def visit_Call(self, node):
		self.add_to_snapshot(self.resolver.resolve_value(node))

	def visit_AnnAssign(self, node):
		resolved_value = self.resolver.resolve_value(node.value)
		self.add_to_snapshot(resolved_value)

		resolved_target = self.resolver.resolve_target(node.target)
		self.resolver.process_assignment(resolved_target, resolved_value)
		
		if len(resolved_value) == 1 and resolved_value.ref().type_expr.typedef == Typing.get_type("Any"):
			self.generic_visit(node)

	def visit_Assign(self, node):
		resolved_value = self.resolver.resolve_value(node.value)
		self.add_to_snapshot(resolved_value)
		for target in node.targets:
			resolved_target = self.resolver.resolve_target(target)
			self.resolver.process_assignment(resolved_target, resolved_value)
		
		if len(resolved_value) == 1 and resolved_value.ref().type_expr.typedef == Typing.get_type("Any"):
			self.generic_visit(node)
	
	def visit_AugAssign(self, node):
		toAssign = ast.Assign(
			targets=[node.target],
			value=ast.BinOp(
				left=copy.deepcopy(node.target),
				op=node.op,
				right=node.value
			)
		)
		ast.copy_location(toAssign, node)
		ast.copy_location(toAssign.value, node)
		toAssign = ast.fix_missing_locations(toAssign)
		self.visit_Assign(toAssign)
