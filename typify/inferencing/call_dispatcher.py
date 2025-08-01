import ast
import copy
from typify.inferencing.resolver import Resolver
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.function_utils import FunctionUtils
from typify.preprocessing.core import GlobalContext
from typify.inferencing.commons import (
    Builtins,
    Checker
)
from typify.preprocessing.instance_utils import (
	ReferenceSet,
	Instance,
)
from typify.preprocessing.symbol_table import (
    FunctionDefinition,
	ClassDefinition
)

class CallDispatcher:
	def __init__(self, resolver: Resolver, node: ast.Call):
		self.resolver = resolver
		self.node = node
	
	def exec(
			self,
			method: FunctionDefinition,
			inject: Instance = None
		):

		if not method: return ReferenceSet()

		modified_node = copy.deepcopy(self.node)

		if inject:
			modified_node.args.insert(0, ast.Constant(0))

		param_map = method.parameters
		argmap = FunctionUtils.map_call_arguments(modified_node, param_map, self.resolver)
		
		if inject:
			first_param = next(iter(argmap.values()))
			first_param.refset = ReferenceSet(inject)
		
		prev = GlobalContext.symbol_map[self.resolver.symbol]
		result = FunctionUtils.exec_function(
			inject,
			argmap, 
			method, 
			self.resolver.call_stack
		)
		GlobalContext.symbol_map[self.resolver.symbol] = prev
		return result

	def dispatch(self) -> ReferenceSet:
		result = ReferenceSet()
		if isinstance(self.node.func, ast.Attribute):
			callers_set = self.resolver.resolve_value(self.node.func.value)
			for caller in callers_set:
				method_attr = caller.attribute_lookup(self.node.func.attr)
				if not method_attr: continue

				candidate_def = method_attr.get_latest_definition()
				if not candidate_def.refset: continue

				candidate = candidate_def.refset.ref()

				if candidate.instanceof(Builtins.get_type("function")):
					shortcircuit = False
					for decorator in candidate.origin.tree.decorator_list:
						if isinstance(decorator, ast.Name):
							if decorator.id == "classmethod":
								if isinstance(caller.origin, ClassDefinition):
									class_instance = caller
								else:
									class_instance = caller.instantiator.mro[0]
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
						if caller.instanceof(Builtins.get_type("module")):
							returns = self.exec(candidate.origin)
						else:
							caller_to_pass = None
							for ci in caller.instantiator.mro:
								if candidate.origin.get_enclosing_class_definition() == ci.origin:
									caller_to_pass = caller
									break
							returns = self.exec(candidate.origin, caller_to_pass)
						result.update(returns)

				elif Checker.is_type(candidate):
					result.add(self.dispatch_instance(candidate))
		else:
			candidates = self.resolver.resolve_value(self.node.func)
		
			for candidate in candidates:
				if candidate.instanceof(Builtins.get_type("function")):
					function_table = candidate.origin
					returns = self.exec(function_table)
					result.update(returns)

				elif Checker.is_type(candidate):
					result.add(self.dispatch_instance(candidate))
		return result
	
	def dispatch_instance(self, candidate: Instance) -> Instance:
		class_table = candidate.origin
		instance = TypeUtils.instantiate_with_args(class_table)
		
		if Checker.match_origin(class_table, Builtins.get_type("type")):
			instance.origin = Builtins.get_type("type")

		init_attr = instance.attribute_lookup("__init__")
		init_def = init_attr.get_latest_definition()
		init_method = init_def.refset.ref().origin

		self.exec(init_method, instance)
		return instance

