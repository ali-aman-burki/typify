import ast
import copy

from collections import defaultdict
from dataclasses import (
    dataclass,
    field
)

from typify.preprocessing.module_meta import ModuleMeta
from typify.inferencing.function_utils import FunctionUtils
from typify.preprocessing.dependency_utils import DependencyUtils
from typify.inferencing.mro import MROBuilder
from typify.inferencing.resolver import Resolver
from typify.inferencing.typeutils import TypeUtils
from typify.preprocessing.core import GlobalContext
from typify.inferencing.expression import (
    TypeExpr, 
	PackedExpr,
    AliasParser
)
from typify.inferencing.commons import (
	Builtins,
	Future,
	Singletons,
	ArgTuple,
	Checker,
	ParameterEntry
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

@dataclass(eq=False)
class Varnotation:
	annotation: Instance = None

@dataclass
class DeferredAnnotations:
	resolver: Resolver
	on: bool = False
	strings: set[str] = field(default_factory=set)
	holders: dict[ParameterEntry | Instance | PackedExpr | Varnotation, str] = field(default_factory=dict)

	def compute(self):
		lookup: dict[str, Instance] = {}

		for string in self.strings:
			node = ast.parse(string, mode='eval').body
			refset = self.resolver.resolve_value(node)
			if refset:
				ref = refset.ref()
				lookup[string] = ref.resolve_fully(self.resolver)
		
		for k, v in self.holders.items():
			from_lookup = lookup.get(v)
			if from_lookup:
				if isinstance(k, Instance): k.return_annotation = from_lookup
				elif isinstance(k, PackedExpr): k.base = from_lookup
				elif isinstance(k, ParameterEntry): k.annotation = from_lookup
				elif isinstance(k, Varnotation): k.annotation = from_lookup

class Executor(ast.NodeVisitor):
	def __init__(
			self, 
			module_meta: ModuleMeta,
			symbol: Module | ClassDefinition | FunctionDefinition,
			namespace: Instance | CallFrame, 
			caller: Instance,
			arguments: dict[str, ArgTuple],
			call_stack: list,
			tree: ast.AST,
			deferred_annotations: DeferredAnnotations = None,
			snapshot_log: list[ReferenceSet] = None
		):

		from typify.inferencing.generics.utils import GenericUtils

		self.module_meta = module_meta
		self.symbol = symbol
		self.namespace = namespace
		self.caller = caller
		self.call_stack = call_stack
		self.tree = tree
		self.snapshot_log = snapshot_log if snapshot_log else []

		self.import_stmt_count = 0

		self.returns = ReferenceSet()
		self.resolver = Resolver(
			self.module_meta, 
			self.symbol, 
			self.namespace,
			self.call_stack
		)

		self.deferred_annotations = deferred_annotations or DeferredAnnotations(self.resolver)

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
			
			fobject = GlobalContext.function_object_map[self.symbol]
			annotation = fobject.parameters[argname].annotation

			if annotation and caller:
				GenericUtils.register_annotation(
					annotation=annotation,
					type_expr=refset.as_type(),
					classdef=self.symbol.get_enclosing_class_definition(),
					genconstruct=caller.genconstruct,
				)

			if self.module_meta.fslots:
				position = (fobject.tree.lineno, fobject.tree.col_offset)
				self.module_meta.fslots[position][2][argname] = merged.refset

	def execute(self) -> ReferenceSet: 
		from typify.inferencing.generics.utils import GenericUtils
		
		fobject = GlobalContext.function_object_map.get(self.symbol)
		if isinstance(self.namespace, CallFrame) and FunctionUtils.is_stub(fobject.tree):
			if fobject.return_annotation and fobject.return_annotation.instantiator:
				concsubs = {}
				if self.caller:
					gencons = self.caller.genconstruct.get(self.symbol.get_enclosing_class_definition())
					if gencons:
						concsubs = gencons.concsubs
				type_expr = AliasParser.annotation_to_typeexpr(fobject.return_annotation, concsubs)
				result = TypeUtils.instantiate_from_type_expr(type_expr)
				self.returns.update(result)
				self.symbol.refset.update(result)

				if self.module_meta.fslots:
					position = (fobject.tree.lineno, fobject.tree.col_offset)
					self.module_meta.fslots[position][3] = self.symbol.refset
				
				return self.returns

		self.visit(self.tree)
		if isinstance(self.namespace, CallFrame):
			if not TypeUtils.has_complete_return(self.tree.body):
				self.returns.add(Singletons.get("None"))
				self.symbol.refset.add(Singletons.get("None"))
			
			if fobject.return_annotation and fobject.return_annotation.instantiator and self.caller:
				GenericUtils.register_annotation(
					annotation=fobject.return_annotation,
					type_expr=self.returns.as_type(),
					classdef=self.symbol.get_enclosing_class_definition(),
					genconstruct=self.caller.genconstruct
				)

			if self.module_meta.fslots:
				position = (fobject.tree.lineno, fobject.tree.col_offset)
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
		self.add_to_snapshot(resolved)
		self.symbol.refset.update(resolved)
		self.returns.update(resolved)

	def visit_Import(self, node):
		position = (node.lineno, node.col_offset)
		defkey = (self.module_meta.table, position)
		
		self.import_stmt_count += 1

		for alias in node.names:
			name = alias.asname if alias.asname else alias.name.split(".")[0]
			self.symbol.get_name(name).merge_definition(NameDefinition(defkey))
			self.namespace.get_name(name).set_definition(NameDefinition(defkey))

			object_chain = DependencyUtils.resolve_module_objects(
				defkey, 
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
		
		self.import_stmt_count += 1

		object_chain = DependencyUtils.resolve_module_objects(
			defkey,
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

					if lat_def.refset and self.import_stmt_count == 1 and isinstance(self.symbol, Module):
						fobject = GlobalContext.symbol_map.get(Future.module())
						if fobject:
							annobject = fobject.names["annotations"].get_plausible_refset().ref()
							if lat_def.refset.ref() == annobject:
								self.deferred_annotations.on = True
				else:
					fqn = DependencyUtils.to_absolute_name(
						self.module_meta.table, 
						node.module, 
						node.level
					)
					fqn += f".{alias.name}"
					new_object_chain = DependencyUtils.resolve_module_objects(
						defkey,
						fqn
					)
					if not new_object_chain: continue

					deftable = NameDefinition(defkey)
					deftable.refset.add(new_object_chain[-1])
					self.symbol.get_name(name).merge_definition(deftable)
					self.namespace.get_name(name).merge_definition(deftable)
				
				reference = self.namespace.get_name(name).lookup_definition(defkey).refset
				self.add_to_snapshot(reference)

		self.deferred_annotations.compute()
		self.generic_visit(node)

	#TODO: add support for multiple possible candidates for a single base
	def visit_ClassDef(self, class_tree: ast.ClassDef):
		from typify.inferencing.generics.utils import GenericUtils

		name = class_tree.name
		position = (class_tree.lineno, class_tree.col_offset)
		defkey = (self.module_meta.table, position)

		class_table = self.symbol.get_class(name)
		entering_symbol = class_table.get_definition(ClassDefinition(defkey))

		builtins_module_object = GlobalContext.symbol_map.get(Builtins.module())
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
		
		inside_function = False
		current = self.symbol

		while current:
			if isinstance(current, FunctionDefinition):
				inside_function = True
				break
			current = current.parent

		if not inside_function:
			entering_namespace = GlobalContext.symbol_map.setdefault(
				entering_symbol,
				TypeUtils.instantiate_with_args(
					Builtins.get_type("type"),
					[TypeExpr(entering_symbol)]
				)
			)
		else:
			entering_namespace = TypeUtils.instantiate_with_args(
				Builtins.get_type("type"),
				[TypeExpr(entering_symbol)]
			)
			GlobalContext.symbol_map[entering_symbol] = entering_namespace
		
		entering_namespace.update_type_info(
			Builtins.get_type("type"), 
			[TypeExpr(entering_symbol)]
		)

		entering_namespace.origin = entering_symbol
		Executor(
			module_meta=self.module_meta,
			symbol=entering_symbol,
			namespace=entering_namespace,
			caller=self.caller,
			arguments={},
			call_stack=self.call_stack,
			tree=ast.Module(class_tree.body, type_ignores=[]),
			deferred_annotations=self.deferred_annotations,
			snapshot_log=self.snapshot_log
		).execute()

		deftable = NameDefinition(defkey)
		deftable.refset.add(entering_namespace)
		self.symbol.get_name(name).merge_definition(deftable)
		self.namespace.get_name(name).set_definition(deftable)

		entering_symbol.mro = MROBuilder.build_mro(entering_namespace)

		self.add_to_snapshot(deftable.refset)
		self.deferred_annotations.compute()

	def _process_annotation(self, node: ast.Expr, obj: Instance | PackedExpr | ParameterEntry | Varnotation):
		string = ""
		if self.deferred_annotations.on:
			if isinstance(node, ast.Constant):
				if isinstance(node.value, str):
					string = node.value
					self.deferred_annotations.strings.add(string)
			else:
				string = ast.unparse(node)
				self.deferred_annotations.strings.add(string)
			
			self.deferred_annotations.holders[obj] = string
		else:
			refset = self.resolver.resolve_value(node)
			if refset:
				ref = refset.ref()
				if ref.instanceof(Builtins.get_type("str")):
					self.deferred_annotations.strings.add(ref.cval)
					self.deferred_annotations.holders[obj] = ref.cval
				else:
					if isinstance(obj, Instance):
						obj.return_annotation = ref
					elif isinstance(obj, PackedExpr):
						obj.base = ref
					elif isinstance(obj, ParameterEntry):
						obj.annotation = ref
					elif isinstance(obj, Varnotation):
						obj.annotation = ref

					strobjects = ref.collect_str_objects()
					strholders = ref.collect_str_holders()
					if strobjects:
						self.deferred_annotations.strings.update([o.cval for o in strobjects])
						self.deferred_annotations.holders.update(strholders)

	def visit_FunctionDef(self, func_tree: ast.FunctionDef | ast.AsyncFunctionDef):
		position = (func_tree.lineno, func_tree.col_offset)
		defkey = (self.module_meta.table, position)
		name = func_tree.name

		deftable = NameDefinition(defkey)
		self.symbol.get_name(name).merge_definition(deftable)
		self.namespace.get_name(name).set_definition(deftable)

		function_table = self.symbol.get_function(name)
		function_def = function_table.merge_definition(FunctionDefinition(defkey))

		if not isinstance(self.namespace, CallFrame):
			func_obj = GlobalContext.function_object_map.setdefault(
				function_def,
				TypeUtils.instantiate_with_args(Builtins.get_type("function"))
			)
		else:
			func_obj = TypeUtils.instantiate_with_args(Builtins.get_type("function"))
			GlobalContext.function_object_map[function_def] = func_obj
		
		func_obj.update_type_info(Builtins.get_type("function"))
		func_obj.origin = function_def
		func_obj.tree = func_tree
		func_obj.parameters = FunctionUtils.collect_parameters(
			func_tree, 
			self.resolver, 
		)

		if func_tree.returns:
			self._process_annotation(func_tree.returns, func_obj)

		for k, v in func_obj.parameters.items():
			if v.node:
				self._process_annotation(v.node, v)

			ndef = NameDefinition(v.defkey)
			ndef.refset = v.refset.copy()
			mdef = function_def.get_name(k).set_definition(ndef)
			if self.module_meta.fslots:
				self.module_meta.fslots[position][2][k] = mdef.refset

		deftable = NameDefinition(defkey)
		deftable.refset.add(func_obj)
		self.symbol.get_name(name).merge_definition(deftable)
		self.namespace.get_name(name).merge_definition(deftable)

		self.add_to_snapshot(deftable.refset)
		self.deferred_annotations.compute()
	
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
		if arefset:
			annotation = arefset.ref().resolve_fully(self.resolver)
			if self.caller and not annotation.instanceof(Builtins.get_type("str")):
				GenericUtils.register_annotation(
					annotation=annotation,
					type_expr=resolved_value.as_type(),
					classdef=self.symbol.get_enclosing_class_definition(),
					genconstruct=self.caller.genconstruct,
				)

		to_pass = ast.Constant(ast.unparse(node.annotation))
		if isinstance(node.annotation, ast.Constant):
			if isinstance(node.annotation.value, str):
				to_pass = node.annotation
			 
		self._process_annotation(to_pass, Varnotation())

		resolved_target = self.resolver.resolve_target(node.target)
		self.resolver.process_assignment(resolved_target, resolved_value)
		self.deferred_annotations.compute()

	def visit_Assign(self, node):
		resolved_value = self.resolver.resolve_value(node.value)
		self.add_to_snapshot(resolved_value)
		for target in node.targets:
			resolved_target = self.resolver.resolve_target(target)
			self.resolver.process_assignment(resolved_target, resolved_value)
		self.deferred_annotations.compute()
		
	
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
