import ast
import copy

from typify.preprocessing.instance_utils import (
	ReferenceSet,
	Instance,
)
from typify.preprocessing.symbol_table import FunctionDefinition
from typify.inferencing.resolver import Resolver
from typify.inferencing.commons import Builtins
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.function_utils import FunctionUtils
from typify.logging import logger

class CallDispatcher:
	def __init__(self, resolver: Resolver, node: ast.Call):
		self.resolver = resolver
		self.node = node
	
	def exec(
			self,
			method: FunctionDefinition,
			inject: Instance = None
		):

		modified_node = copy.deepcopy(self.node)

		if inject:
			modified_node.args.insert(0, ast.Constant(0))

		param_map = method.parameters
		argmap = FunctionUtils.map_call_arguments(modified_node, param_map, self.resolver)
		
		if inject:
			first_param = next(iter(argmap.values()))
			first_param.refset = ReferenceSet(inject)
		
		return FunctionUtils.exec_function(
			self.resolver.context, 
			argmap, 
			method, 
			self.resolver.call_stack
		)

	def dispatch(self) -> ReferenceSet:
		result = ReferenceSet()
		if isinstance(self.node.func, ast.Attribute):
			callers_set = self.resolver.resolve_value(self.node.func.value)
			for caller in callers_set:
				method_attr = self.resolver.attribute_lookup(caller, self.node.func.attr)
				if not method_attr: continue

				candidate_def = method_attr.get_latest_definition()
				candidate = candidate_def.refset.ref()

				if candidate.type_expr.typedef == Builtins.get_type("function"):
					shortcircuit = False
					for decorator in candidate.origin.tree.decorator_list:
						if isinstance(decorator, ast.Name):
							if decorator.id == "classmethod":
								class_instance = caller.type_expr.typedef.mro[0]
								returns = self.exec(candidate.origin, class_instance)
								result.update(returns)
								shortcircuit = True
								break
							elif decorator.id == "staticmethod":
								returns = self.exec(candidate.origin)
								result.update(returns)
								shortcircuit = True
								break
					
					if not shortcircuit:
						if caller.type_expr.typedef == Builtins.get_type("module"):
							returns = self.exec(candidate.origin)
						else:
							returns = self.exec(candidate.origin, caller)
						result.update(returns)

				elif candidate.type_expr.typedef == Builtins.get_type("type"):
					result.add(self.dispatch_instance(candidate))
		else:
			candidates = self.resolver.resolve_value(self.node.func)
		
			for candidate in candidates:
				if candidate.type_expr.typedef == Builtins.get_type("function"):
					function_table = candidate.origin
					returns = self.exec(function_table)
					result.update(returns)

				elif candidate.type_expr.typedef == Builtins.get_type("type"):
					result.add(self.dispatch_instance(candidate))
		return result
	
	def dispatch_instance(self, candidate: Instance) -> Instance:
		class_table = candidate.origin
		instance = TypeUtils.instantiate(class_table)
		
		init_attr = self.resolver.attribute_lookup(instance, "__init__")
		init_def = init_attr.get_latest_definition()
		init_method = init_def.refset.ref().origin

		self.exec(init_method, instance)
		return instance

