import ast

from typify.preprocessing.symbol_table import (
	InstanceTable,
	DefinitionTable
)
from typify.inferencing.resolver import Resolver
from typify.inferencing.commons import Builtins
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.function_utils import FunctionUtils

class CallDispatcher:
	def __init__(self, resolver: Resolver, node: ast.Call):
		self.resolver = resolver
		self.node = node
	
	def inject_first_and_run(
			self,
			inject: InstanceTable, 
			method: DefinitionTable
		):

		param_map = method.parameters
		self.node.args.insert(0, ast.Constant(0))

		argmap = FunctionUtils.map_call_arguments(self.node, param_map, self.resolver)
		first_param = next(iter(argmap.values()))
		first_param.points_to = {inject}

		FunctionUtils.run_function(
			self.resolver.context, 
			argmap, 
			method, 
			self.resolver.call_stack
		)

	def dispatch(self) -> set[InstanceTable]:
		candidates = self.resolver.resolve_value(self.node.func)
		results = set()
		for candidate in candidates:
			if candidate.type_expr.typedef == Builtins.get_type("function"):
				function_table = candidate.origin
				param_map = function_table.parameters
				argmap = FunctionUtils.map_call_arguments(self.node, param_map, self.resolver)
				returns = FunctionUtils.run_function(
					self.resolver.context, 
					argmap, 
					function_table, 
					self.resolver.call_stack
				)
				results.update(returns)
			elif candidate.type_expr.typedef == Builtins.get_type("type"):
				class_table = candidate.origin
				instance = TypeUtils.instantiate(class_table)
				results.add(instance)
				
				init_attr = self.resolver.attribute_lookup(instance, "__init__")
				init_def = init_attr.get_latest_definition()
				init_method = next(iter(init_def.points_to)).origin

				self.inject_first_and_run(instance, init_method)

		return results
