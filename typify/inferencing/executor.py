import ast
import copy
from collections import defaultdict

from typify.preprocessing.module_meta import ModuleMeta
from typify.inferencing.function_utils import FunctionUtils
from typify.preprocessing.dependency_utils import DependencyUtils
from typify.inferencing.mro import MROBuilder
from typify.inferencing.resolver import Resolver
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.expression import TypeExpr, AliasParser
from typify.inferencing.commons import (
	Context,
	Builtins,
	ConstantObjects,
	ArgTuple,
	Checker
)
from typify.preprocessing.symbol_table import (
	Module,
	ClassDefinition,
	FunctionDefinition,
	NameDefinition,
	CallFrame
)

from typify.preprocessing.instance_utils import (
	Instance,
	ReferenceSet
)

class Executor(ast.NodeVisitor):
	def __init__(
			self, 
			context: Context,
			module_meta: ModuleMeta,
			symbol: Module | ClassDefinition | FunctionDefinition,
			namespace: Instance, 
			caller: Instance,
			arguments: dict[str, ArgTuple],
			call_stack: list,
			tree: ast.AST,
			snapshot_log: list[ReferenceSet] = None
		):

		from typify.inferencing.generics.utils import GenericUtils

		self.context = context
		self.module_meta = module_meta
		self.symbol = symbol
		self.namespace = namespace
		self.caller = caller
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

			ndef = NameDefinition(defkey)
			ndef.refset.update(refset)
			namespace_name.set_definition(ndef)
			merged = symbol_name.merge_definition(ndef)

			annotation = self.symbol.parameters[argname].annotation

			if annotation and caller:
				GenericUtils.register_annotation(
					annotation=annotation,
					type_expr=refset.as_type(),
					classdef=self.symbol.get_enclosing_class_definition(),
					genconstruct=caller.genconstruct,
				)

			if self.module_meta.fslots:
				position = (self.symbol.tree.lineno, self.symbol.tree.col_offset)
				self.module_meta.fslots[position][2][argname] = merged.refset

	def execute(self) -> ReferenceSet: 
		from typify.inferencing.generics.utils import GenericUtils
		
		if isinstance(self.namespace, CallFrame) and FunctionUtils.is_stub(self.symbol.tree):
			if self.symbol.return_annotation:
				concsubs = {}
				if self.caller:
					gencons = self.caller.genconstruct.get(self.symbol.get_enclosing_class_definition())
					if gencons:
						concsubs = gencons.concsubs
				type_expr = AliasParser.annotation_to_typeexpr(self.symbol.return_annotation, concsubs)
				result = TypeUtils.instantiate_from_type_expr(type_expr)
				self.returns.update(result)
				self.symbol.refset.update(result)
				return self.returns

		self.visit(self.tree)
		if isinstance(self.namespace, CallFrame):
			if not TypeUtils.has_complete_return(self.tree.body):
				self.returns.add(ConstantObjects.get("NoneType"))
				self.symbol.refset.add(ConstantObjects.get("NoneType"))
			
			if self.symbol.return_annotation and self.caller:
				GenericUtils.register_annotation(
					annotation=self.symbol.return_annotation,
					type_expr=self.returns.as_type(),
					classdef=self.symbol.get_enclosing_class_definition(),
					genconstruct=self.caller.genconstruct
				)

			if self.module_meta.fslots:
				position = (self.symbol.tree.lineno, self.symbol.tree.col_offset)
				self.module_meta.fslots[position][3] = self.symbol.refset
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

	def visit_Import(self, node):
		position = (node.lineno, node.col_offset)
		defkey = (self.module_meta.table, position)
		for alias in node.names:
			name = alias.asname if alias.asname else alias.name.split(".")[0]
			self.symbol.get_name(name).merge_definition(NameDefinition(defkey))
			self.namespace.get_name(name).set_definition(NameDefinition(defkey))

			object_chain = DependencyUtils.resolve_module_objects(
				defkey, 
				self.context.libs, 
				self.context.sysmodules, 
				alias.name
			)
			if not object_chain:
				deftable = NameDefinition(defkey)
				self.symbol.get_name(name).merge_definition(deftable)
				self.namespace.get_name(name).merge_definition(deftable)
				continue
			
			deftable = NameDefinition(defkey)
			deftable.refset.add(object_chain[-1] if alias.asname else object_chain[0])
			self.symbol.get_name(name).merge_definition(deftable)
			self.namespace.get_name(name).merge_definition(deftable)

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
				lat_def = NameDefinition(defkey)
				lat_def.refset = name.get_plausible_refset().copy()
				self.namespace.get_name(name.id).set_definition(lat_def)
				self.add_to_snapshot(lat_def.refset)
		else:
			for alias in node.names:
				name = alias.asname if alias.asname else alias.name
				self.symbol.get_name(name).merge_definition(NameDefinition(defkey))
				self.namespace.get_name(name).set_definition(NameDefinition(defkey))
				
				if not object_chain: 
					deftable = NameDefinition(defkey)
					self.symbol.get_name(name).merge_definition(deftable)
					self.namespace.get_name(name).merge_definition(deftable)
					return
				
				if alias.name in object_chain[-1].names:
					mname = object_chain[-1].names[alias.name]
					
					lat_def = NameDefinition(defkey)
					lat_def.refset = mname.get_plausible_refset().copy()

					self.symbol.get_name(name).merge_definition(lat_def)
					self.namespace.get_name(name).merge_definition(lat_def)
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
					if not new_object_chain: continue

					deftable = NameDefinition(defkey)
					deftable.refset.add(new_object_chain[-1])
					self.symbol.get_name(name).merge_definition(deftable)
					self.namespace.get_name(name).merge_definition(deftable)
				
				reference = self.namespace.get_name(name).lookup_definition(defkey).refset
				self.add_to_snapshot(reference)
				
		self.generic_visit(node)

	#TODO: add support for multiple possible candidates for a single base
	def visit_ClassDef(self, class_tree: ast.ClassDef):
		from typify.inferencing.generics.utils import GenericUtils

		name = class_tree.name
		position = (class_tree.lineno, class_tree.col_offset)
		defkey = (self.module_meta.table, position)

		class_table = self.symbol.get_class(name)
		entering_symbol = class_table.get_definition(ClassDefinition(defkey))

		builtins_module_object = self.context.symbol_map.get(Builtins.module())
		entering_symbol.bases.clear()
		entering_symbol.genbases.clear()

		for base in class_tree.bases:
			base_inst_set = self.resolver.resolve_value(base)
			if base_inst_set:
				base_inst = base_inst_set.ref()
				if base_inst.instanceof(Builtins.get_type("NoneType")): continue

				if Checker.is_generic_alias(base_inst):
					entering_symbol.genbases.append(base_inst)
					base_inst = base_inst.packed_expr.base
				
				entering_symbol.bases.append(base_inst)
				self.add_to_snapshot(ReferenceSet(base_inst))

		if not entering_symbol.bases:
			if builtins_module_object:
				object_class = builtins_module_object.names.get("object")
				if object_class:
					object_def = object_class.get_latest_definition()
					instance = object_def.refset.ref()
					entering_symbol.bases.append(instance)
					self.add_to_snapshot(ReferenceSet(instance))
			
		gentree = { entering_symbol: GenericUtils.build_gentree(entering_symbol) }
		entering_symbol.genconstruct = GenericUtils.flatten_gentree(gentree)
		
		entering_namespace = self.context.symbol_map.setdefault(
			entering_symbol,
			TypeUtils.instantiate_with_args(
				Builtins.get_type("type"),
				[TypeExpr(entering_symbol)]
			)
		)
		entering_namespace.update_type_info(
			Builtins.get_type("type"), 
			[TypeExpr(entering_symbol)]
		)

		entering_namespace.origin = entering_symbol
		Executor(
			context=self.context,
			module_meta=self.module_meta,
			symbol=entering_symbol,
			namespace=entering_namespace,
			caller=self.caller,
			arguments={},
			call_stack=self.call_stack,
			tree=ast.Module(class_tree.body, type_ignores=[]),
			snapshot_log=self.snapshot_log
		).execute()

		deftable = NameDefinition(defkey)
		deftable.refset.add(entering_namespace)
		self.symbol.get_name(name).merge_definition(deftable)
		self.namespace.get_name(name).set_definition(deftable)

		entering_symbol.mro = MROBuilder.build_mro(entering_namespace)

		self.add_to_snapshot(deftable.refset)
		
	def visit_FunctionDef(self, func_tree: ast.FunctionDef | ast.AsyncFunctionDef):
		position = (func_tree.lineno, func_tree.col_offset)
		defkey = (self.module_meta.table, position)
		name = func_tree.name

		deftable = NameDefinition(defkey)
		self.symbol.get_name(name).merge_definition(deftable)
		self.namespace.get_name(name).set_definition(deftable)

		function_table = self.symbol.get_function(name)
		function_def = function_table.merge_definition(FunctionDefinition(defkey))
		function_def.tree = func_tree
		function_def.parameters = FunctionUtils.collect_parameters(func_tree, self.resolver)

		if func_tree.returns:
			arefset = self.resolver.resolve_value(func_tree.returns)
			if arefset: function_def.return_annotation = arefset.ref()

		for k, v in function_def.parameters.items():
			ndef = NameDefinition(v.defkey)
			ndef.refset = v.refset.copy()
			mdef = function_def.get_name(k).set_definition(ndef)
			if self.module_meta.fslots:
				self.module_meta.fslots[position][2][k] = mdef.refset

		func_obj = self.context.function_object_map.setdefault(
			function_def,
			TypeUtils.instantiate_with_args(Builtins.get_type("function"))
		)
		func_obj.update_type_info(Builtins.get_type("function"))
		func_obj.origin = function_def

		deftable = NameDefinition(defkey)
		deftable.refset.add(func_obj)
		self.symbol.get_name(name).merge_definition(deftable)
		self.namespace.get_name(name).merge_definition(deftable)

		self.add_to_snapshot(deftable.refset)
	
	def visit_AsyncFunctionDef(self, node):
		self.visit_FunctionDef(node)

	def visit_Call(self, node):
		self.add_to_snapshot(self.resolver.resolve_value(node))
	
	def visit_Subscript(self, node):
		self.add_to_snapshot(self.resolver.resolve_value(node))

	def visit_AnnAssign(self, node):
		from typify.inferencing.generics.utils import GenericUtils

		resolved_value = self.resolver.resolve_value(node.value)
		self.add_to_snapshot(resolved_value)

		arefset = self.resolver.resolve_value(node.annotation)
		if arefset and self.caller:
			annotation = arefset.ref()
			GenericUtils.register_annotation(
				annotation=annotation,
				type_expr=resolved_value.as_type(),
				classdef=self.symbol.get_enclosing_class_definition(),
				genconstruct=self.caller.genconstruct,
			)

		resolved_target = self.resolver.resolve_target(node.target)
		self.resolver.process_assignment(resolved_target, resolved_value)

	def visit_Assign(self, node):
		resolved_value = self.resolver.resolve_value(node.value)
		self.add_to_snapshot(resolved_value)
		for target in node.targets:
			resolved_target = self.resolver.resolve_target(target)
			self.resolver.process_assignment(resolved_target, resolved_value)
	
	def visit_AugAssign(self, node):
		from typify.inferencing.desugar import Desugar
		from typify.inferencing.call_dispatcher import CallDispatcher

		desugared = Desugar.to_dunder(node)
		dispatcher = CallDispatcher(self.resolver, desugared)
		refset = dispatcher.dispatch()

		if not refset:
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
		else:
			resolved_target = self.resolver.resolve_target(node.target)
			self.resolver.process_assignment(resolved_target, refset)
