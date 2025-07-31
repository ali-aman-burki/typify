import ast

from typify.logging import logger
from typify.inferencing.resolver import Resolver
from typify.preprocessing.instance_utils import (
    ReferenceSet,
    Instance
)
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.expression import TypeExpr
from typify.inferencing.commons import (
	Typing, 
	Builtins,
	Context,
	ParameterEntry,
	ArgTuple
)
from typify.inferencing.call_stack import (
    CallStack,
    CallSignature,
)
from typify.preprocessing.symbol_table import (
	FunctionDefinition, 
	CallFrame,
)

class FunctionUtils:

	def is_stub(func_node):
		if len(func_node.body) != 1:
			return False

		stmt = func_node.body[0]

		return (
			isinstance(stmt, ast.Expr)
			and isinstance(stmt.value, ast.Constant)
			and stmt.value.value is Ellipsis
		)

	@staticmethod
	def construct_executor(
		context: Context, 
		caller: Instance,
		arguments: dict[str, ArgTuple], 
		function_table: FunctionDefinition,
		call_stack: CallStack
	):
		from typify.inferencing.executor import Executor
		
		tree = function_table.tree
		call_frame = CallFrame(f"frame@{function_table.parent.fqn}")
		call_frame.parent = function_table.parent

		mod = call_frame.get_enclosing_module() 
		context.symbol_map[function_table] = call_frame
		context_meta = context.meta_map[mod]

		executor = Executor(
			context=context,
			module_meta=context_meta,
			symbol=function_table,
			namespace=call_frame, 
			caller=caller,
			arguments=arguments,
			call_stack=call_stack,
			tree=ast.Module(tree.body, type_ignores=[]), 
			snapshot_log=[]
		)

		return executor

	@staticmethod
	def exec_function(
		context: Context, 
		caller: Instance,
		arguments: dict[str, ArgTuple], 
		function_table: FunctionDefinition,
		call_stack: CallStack
	) -> ReferenceSet:

		executor = FunctionUtils.construct_executor(
			context, 
			caller,
			arguments, 
			function_table, 
			call_stack
		)
		sigkey = CallSignature(function_table, arguments)
		signature = call_stack.get(sigkey) or sigkey

		if not call_stack.contains(signature):
			call_stack.push(signature)
			logger.debug(f"🆕 Pushed: {repr(signature)}")

			returns = executor.execute()
			signature.snapshot = executor.snapshot()
			signature.returns.update(returns)

			call_stack.pop()
			logger.debug(f"✅ Popped: {repr(signature)}")
			return returns
		else:
			traced = call_stack.trace(signature)
			logger.debug(f"⚠️  Recursive SCC detected: {[repr(t) for t in traced]}", 1)

			if not any(sig.running for sig in traced):
				for sig in traced:
					sig.running = True

				iteration = 0
				while True:
					logger.debug(f"🔄 Fixpoint Iteration {iteration}", 1)
					changed = False

					for sig in traced:
						logger.debug(f"🚀 Running: {repr(sig)}", 1)
						executor = FunctionUtils.construct_executor(
							context,
							caller,
							sig.arguments,
							sig.function_table,
							call_stack
						)

						snapshot_before = sig.snapshot
						returns = executor.execute()
						snapshot_after = executor.snapshot()

						sig.returns = returns.copy()
						sig.snapshot = snapshot_after

						logger.debug(f"  ▸ Before snapshot: {snapshot_before}")
						logger.debug(f"  ▸ After snapshot:  {snapshot_after}")

						if snapshot_before != snapshot_after:
							changed = True

					if not changed:
						logger.debug(f"✅ Fixpoint reached — snapshots stabilized.", 1)
						break

					iteration += 1

				for sig in traced:
					sig.running = False

			logger.debug(f"📤 Returning from: {repr(signature)} with returns = {signature.returns}")
			return signature.returns
	
	@staticmethod
	def map_call_arguments(
		call_node: ast.Call,
		parameters: dict[str, ParameterEntry],
		resolver: Resolver,
	) -> dict[str, ArgTuple]:

		resolved_args: dict[str, ArgTuple] = {}
		vararg_param = next((p for p in parameters.values() if p.is_vararg), None)

		positional_param_entries = [
			p for p in parameters.values()
			if not (p.is_vararg or p.is_kwarg or p.is_kwonly)
			and p.name not in {kw.arg for kw in call_node.keywords if kw.arg is not None}
		]

		for i, arg_node in enumerate(call_node.args[:len(positional_param_entries)]):
			name = positional_param_entries[i].name
			refset = ReferenceSet()
			defkey = positional_param_entries[i].defkey

			for instance in resolver.resolve_value(arg_node):
				refset.add(instance)

			resolved_args[name] = ArgTuple(refset, defkey)

		extra_args = call_node.args[len(positional_param_entries):]

		if vararg_param and extra_args:
			name = vararg_param.name
			refset = ReferenceSet()
			defkey = vararg_param.defkey

			store = []
			typeargs = []

			for elt in extra_args:
				resolved = resolver.resolve_value(elt)
				unified = TypeUtils.unify(resolved)
				typeargs.append(unified)
				store.append(resolved)

			instance = TypeUtils.instantiate_with_args(Builtins.get_type("tuple"), typeargs)
			instance.store = store
			refset.add(instance)

			resolved_args[name] = ArgTuple(refset, defkey)

		for kw in call_node.keywords:
			if kw.arg is None:
				continue
			if kw.arg in parameters:
				kwentry = parameters[kw.arg]
				name = kw.arg
				refset = ReferenceSet()
				defkey = kwentry.defkey
				
				for instance in resolver.resolve_value(kw.value):
					refset.add(instance)

				resolved_args[name] = ArgTuple(refset, defkey)

		for pname, param_entry in parameters.items():
			if pname not in resolved_args:
				resolved_args[pname] = ArgTuple(param_entry.refset, param_entry.defkey)

		return resolved_args

	#TODO: add support *varargs and **kwargs
	@staticmethod
	def collect_parameters(
		fdef: ast.FunctionDef | ast.AsyncFunctionDef, 
		resolver: Resolver
	) -> dict[str, ParameterEntry]:
		
		args_node = fdef.args
		parameters: dict[str, ParameterEntry] = {}

		def resolve_annotation(arg: ast.arg) -> Instance:
			if arg.annotation:
				results = resolver.resolve_value(arg.annotation)
				if results: return results.ref()
			return None

		def register_arg(
			arg: ast.arg,
			default_value: ast.expr = None,
			*,
			is_posonly=False,
			is_kwonly=False
		) -> ParameterEntry:
			name = arg.arg
			refset = ReferenceSet()
			defkey = (resolver.module_meta.table, (arg.lineno, arg.col_offset))
			
			if default_value is not None:
				for instance in resolver.resolve_value(default_value):
					refset.add(instance)

			entry = ParameterEntry(
				name=name,
				refset=refset,
				defkey=defkey,
				is_posonly=is_posonly,
				is_kwonly=is_kwonly,
				annotation=resolve_annotation(arg),
			)
			parameters[name] = entry
			return entry

		posonly_defaults = [None] * (len(args_node.posonlyargs) - len(args_node.defaults)) + args_node.defaults[:len(args_node.posonlyargs)]
		for arg, default in zip(args_node.posonlyargs, posonly_defaults):
			register_arg(arg, default, is_posonly=True)

		regular_defaults = args_node.defaults[-len(args_node.args):] if args_node.defaults else []
		regular_defaults = [None] * (len(args_node.args) - len(regular_defaults)) + regular_defaults
		for arg, default in zip(args_node.args, regular_defaults):
			register_arg(arg, default)

		if args_node.vararg:
			arg = args_node.vararg
			name = arg.arg
			refset = ReferenceSet()
			defkey = (resolver.module_meta.table, (arg.lineno, arg.col_offset))
			
			refset.add(TypeUtils.instantiate_with_args(Builtins.get_type("tuple")))
			parameters[name] = ParameterEntry(
				name=name,
				refset=refset,
				defkey=defkey,
				is_vararg=True,
				annotation=resolve_annotation(arg),
			)

		for arg, default in zip(args_node.kwonlyargs, args_node.kw_defaults):
			register_arg(arg, default, is_kwonly=True)

		if args_node.kwarg:
			arg = args_node.kwarg
			name = arg.arg
			refset = ReferenceSet()
			defkey = (resolver.module_meta.table, (arg.lineno, arg.col_offset))

			dict_expr = TypeExpr(Builtins.get_type("dict"), [TypeExpr(Builtins.get_type("str")), TypeExpr(Typing.get_type("Any"))])
			dict_instance = TypeUtils.instantiate_from_type_expr(dict_expr)
			refset.update(dict_instance)
			
			parameters[name] = ParameterEntry(
				name=name,
				refset=refset,
				defkey=defkey,
				is_kwarg=True,
				annotation=resolve_annotation(arg),
			)

		return parameters




			
