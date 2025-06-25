import ast
import copy
from collections import defaultdict

from typify.inferencing.typeutils import TypeUtils
from typify.preprocessing.dependency_utils import DependencyUtils
from typify.inferencing.resolver import Resolver
from typify.inferencing.commons import (
	Context,
	Builtins
)
from typify.preprocessing.symbol_table import (
	 InstanceTable,
	 DefinitionTable,
	 Table,
	 ClassTable,
	 FunctionTable
)

class Executor(ast.NodeVisitor):
	def __init__(
			  self, 
			  context: Context,
			  symbol: Table,
			  namespace: InstanceTable, 
			  tree: ast.AST,
			  snapshot_log: list[set[InstanceTable]] = None
		):
		self.context = context
		self.symbol = symbol
		self.namespace = namespace
		self.tree = tree
		self.snapshot_log = snapshot_log if snapshot_log else []

		self.resolver = Resolver(self.context, self.symbol, self.namespace)

	def execute(self): self.visit(self.tree)

	def snapshot(self): 
		result = []
		for points_to in self.snapshot_log:
			counter = defaultdict(int)
			labeled = set()
			for pt in points_to:
				counter[pt.key] += 1
				label = f"{pt.key}#{counter[pt.key]}"
				labeled.add(label)
			result.append(labeled)
		return result

	def add_to_snapshot(self, points_to: set[InstanceTable]):
		self.snapshot_log.append(points_to.copy())

	def visit_Import(self, node):
		position = (node.lineno, node.col_offset)
		defkey = (self.context.module_meta.table, position)
		for alias in node.names:
			namedef = self.resolver.create_name(
				alias.asname if alias.asname else alias.name.split(".")[0], 
				defkey,
				self.namespace,
				self.symbol
			)
			object_chain = DependencyUtils.resolve_module_objects(
				defkey, 
				self.context.libs, 
				self.context.sysmodules, 
				alias.name
			)
			if not object_chain: continue

			namedef.points_to.add(object_chain[-1] if alias.asname else object_chain[0])
			self.add_to_snapshot(namedef.points_to)

		self.generic_visit(node)
	
	def visit_ImportFrom(self, node):
		position = (node.lineno, node.col_offset)
		defkey = (self.context.module_meta.table, position)
		object_chain = DependencyUtils.resolve_module_objects(
			defkey,
			self.context.libs,
			self.context.sysmodules,
			node.module, node.level
		)
		
		if not object_chain: return

		if node.names[0].name == "*":
			result = Table.create_and_transfer_names(object_chain[-1], self.symbol, defkey)
			Table.transfer_names(result, self.namespace)
			for namedef in result.values():
				self.add_to_snapshot(namedef.points_to)
		else:
			for alias in node.names:
				namedef = self.resolver.create_name(
					alias.asname if alias.asname else alias.name, 
					defkey,
					self.namespace,
					self.symbol
				)
				if alias.name in object_chain[-1].names:
					mname = object_chain[-1].names[alias.name]
					mnamedef = mname.get_latest_definition()
					namedef.points_to.update(mnamedef.points_to)
				else:
					fqn = DependencyUtils.to_absolute_name(
						self.context.module_meta.table, 
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
					
					namedef.points_to.add(new_object_chain[-1])
				
				self.add_to_snapshot(namedef.points_to)
				
		self.generic_visit(node)

	def visit_ClassDef(self, class_tree: ast.ClassDef):
		name = class_tree.name
		position = (class_tree.lineno, class_tree.col_offset)
		defkey = (self.context.module_meta.table, position)
		namedef = self.resolver.create_name(
			name,
			defkey,
			self.namespace,
			self.symbol
		)

		class_table = ClassTable(name)
		entering_symbol = class_table.add_definition(DefinitionTable(defkey))
		self.symbol.merge_class(class_table)
		
		entering_namespace = TypeUtils.instantiate(Builtins.get_type("type"))
		entering_namespace.origin = entering_symbol
		namedef.points_to.add(entering_namespace)
		self.add_to_snapshot(namedef.points_to)
	
		self.context.symbol_map[entering_symbol] = entering_namespace

		Executor(
			self.context,
			entering_symbol,
			entering_namespace,
			ast.Module(class_tree.body, type_ignores=[]),
			self.snapshot_log
		).execute()
	
	def visit_FunctionDef(self, func_tree: ast.FunctionDef):
		name = func_tree.name
		position = (func_tree.lineno, func_tree.col_offset)
		defkey = (self.context.module_meta.table, position)
		namedef = self.resolver.create_name(
			name,
			defkey,
			self.namespace,
			self.symbol
		)

		function_table = FunctionTable(name)
		fdef = function_table.add_definition(DefinitionTable(defkey))
		self.symbol.merge_function(function_table)

		func_type = TypeUtils.instantiate(Builtins.get_type("function"))
		namedef.points_to.add(func_type)
		func_type.origin = fdef
		self.add_to_snapshot(namedef.points_to)
	
	def visit_AnnAssign(self, node):
		self.resolver.resolve_target(node.target)
		self.generic_visit(node)

	def visit_Assign(self, node):
		for target in node.targets:
			self.resolver.resolve_target(target)
	
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
