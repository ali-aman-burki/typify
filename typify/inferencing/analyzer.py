import ast
import copy

from typify.preprocessing.symbol_table import (
	Table,
	ClassTable,
	FunctionTable,
	NameTable,
	ModuleTable, 
	InstanceTable,
	DefinitionTable
)
from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.dependency_utils import DependencyUtils
from typify.inferencing.commons import Builtins
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.function_utils import FunctionUtils

from typify.inferencing.commons import bind

class Analyzer(ast.NodeVisitor):
	def __init__(
			self,
			module_meta: ModuleMeta, 
			sysmodules: dict[str, InstanceTable],
			libs: dict[str, LibraryMeta],
			starting_namespace: Table,
		):
		self.module_meta = module_meta
		self.sysmodules = sysmodules
		self.global_namespace = module_meta.table
		self.starting_namespace = starting_namespace
		self.current_namespace = starting_namespace
		self.vslots = self.module_meta.vslots
		self.fslots = self.module_meta.fslots
		self.libs = libs

		self.snapshot_log: list[set[str]] = []
		self.current_namespace_object = None

	def add_to_snapshot(self, points_to: set[InstanceTable]):
		immutable = {pt.key for pt in points_to}
		self.snapshot_log.append(immutable)
	
	def snapshot(self): return [s.copy() for s in self.snapshot_log]

	def push(self, scope_def: Table):
		self.current_namespace = scope_def.get_enclosing_table()
		return scope_def

	def pop(self):
		self.current_namespace = self.current_namespace.get_enclosing_table()
		return self.current_namespace
	
	def process_name(self, name: str, defkey: tuple[ModuleTable, tuple[int, int]]):
		enclosing = self.current_namespace.get_latest_definition()
		nametable = NameTable(name)
		namedef = nametable.add_definition(DefinitionTable(defkey))
		nametable = enclosing.merge_name(nametable)
		self.current_namespace_object.merge_name(nametable)
		return namedef

	def process_target(self, target: ast.AST):
		if isinstance(target, (ast.Tuple, ast.List)):
			for elt in target.elts:
				self.process_target(elt)
		else:
			position = (target.lineno, target.col_offset)
			defkey = (self.global_namespace, position)
			value = (ast.unparse(target), "$unresolved$")
			self.vslots[position] = value

			if isinstance(target, ast.Name):
				self.process_name(target.id, defkey)

	def run(self):
		bind(self.libs)
		self.snapshot_log.clear()
		self.current_namespace = self.starting_namespace
		self.current_namespace_object = None
		self.visit(self.module_meta.tree)
	
	def visit_Module(self, node):
		self.current_namespace_object = self.sysmodules.setdefault(
			self.global_namespace.fqn,
			TypeUtils.instantiate(Builtins.ModuleClass)
		)
		self.generic_visit(node)

	def visit_Import(self, node):
		position = (node.lineno, node.col_offset)
		defkey = (self.global_namespace, position)
		for alias in node.names:
			namedef = self.process_name(alias.asname if alias.asname else alias.name.split(".")[0], defkey)
			object_chain = DependencyUtils.resolve_module_objects(defkey, self.libs, self.sysmodules, alias.name)
			if object_chain:
				namedef.points_to.add(object_chain[-1] if alias.asname else object_chain[0])
				self.add_to_snapshot(namedef.points_to)

		self.generic_visit(node)
	
	def visit_ImportFrom(self, node):
		enclosing = self.current_namespace.get_latest_definition()
		position = (node.lineno, node.col_offset)
		defkey = (self.global_namespace, position)
		object_chain = DependencyUtils.resolve_module_objects(defkey, self.libs, self.sysmodules, node.module, node.level)
		
		if node.names[0].name == "*":
			current_mod_object = self.sysmodules[self.global_namespace.fqn]
			result = Table.create_and_transfer_names(object_chain[-1], enclosing, defkey)
			Table.transfer_names(result, current_mod_object)
			for namedef in result.values():
				self.add_to_snapshot(namedef.points_to)
		else:
			for alias in node.names:
				namedef = self.process_name(alias.asname if alias.asname else alias.name, defkey)
				print(len(object_chain[-1].names))				
				if alias.name in object_chain[-1].names:
					mname = object_chain[-1].names[alias.name]
					mnamedef = mname.get_latest_definition()
					namedef.points_to.update(mnamedef.points_to)
				else:
					fqn = DependencyUtils.to_absolute_name(self.global_namespace, node.module, node.level)
					fqn += f".{alias.name}"
					new_object_chain = DependencyUtils.resolve_module_objects(defkey, self.libs, self.sysmodules, fqn)
					namedef.points_to.add(new_object_chain[-1])
				
				self.add_to_snapshot(namedef.points_to)
				
		self.generic_visit(node)

	def visit_ClassDef(self, node):
		enclosing = self.current_namespace.get_latest_definition()
		position = (node.lineno, node.col_offset)
		defkey = (self.global_namespace, position)
		class_name = node.name
		
		classtable = ClassTable(class_name)
		classdef = classtable.add_definition(DefinitionTable(defkey))
		enclosing.merge_class(classtable)

		cinstance = TypeUtils.instantiate(Builtins.TypeClass)
		namedef = self.process_name(class_name, defkey)
		namedef.points_to.add(cinstance)
		namedef.origin = classdef
		self.add_to_snapshot(namedef.points_to)

		previous_namespace_object = self.current_namespace_object
		self.current_namespace_object = cinstance
		self.push(classdef)
		self.generic_visit(node)
		self.pop()
		self.current_namespace_object = previous_namespace_object

	def visit_FunctionDef(self, node): 
		enclosing = self.current_namespace.get_latest_definition()
		parameters = FunctionUtils.collect_parameters(node, self.global_namespace)
		position = (node.lineno, node.col_offset)
		value = (node.name, parameters, "$unresolved$")
		defkey = (self.global_namespace, position)
		self.fslots[position] = value

		function_name = node.name
		
		functable = FunctionTable(function_name)
		funcdef = functable.add_definition(DefinitionTable(defkey))
		funcdef.tree = node
		funcdef.kind = FunctionUtils.get_function_kind(node)
		enclosing.merge_function(functable)

		finstance = TypeUtils.instantiate(Builtins.FunctionClass)
		finstance.origin = funcdef
		namedef = self.process_name(function_name, defkey)
		namedef.points_to.add(finstance)

		self.add_to_snapshot(namedef.points_to)

	def visit_AsyncFunctionDef(self, node):
		self.visit_FunctionDef(node)

	def visit_AnnAssign(self, node):
		self.process_target(node.target)
		self.generic_visit(node)

	def visit_Assign(self, node):
		for target in node.targets:
			self.process_target(target)
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