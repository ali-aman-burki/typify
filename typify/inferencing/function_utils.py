import ast

from typify.inferencing.resolver import Resolver
from typify.preprocessing.symbol_table import (
	NameTable, 
	DefinitionTable, 
	ModuleTable,
	CallFrameTable,
	InstanceTable
)
from typify.inferencing.typeutils import (
	TypeUtils,
	TypeExpr
)
from typify.inferencing.commons import (
	Typing, 
	Builtins,
	Context
)

from dataclasses import dataclass

@dataclass
class ParameterEntry:
	name: str
	nametable: NameTable
	is_vararg: bool = False
	is_kwarg: bool = False
	is_kwonly: bool = False
	is_posonly: bool = False

class FunctionUtils:

	@staticmethod
	def get_function_kind(fdef: ast.FunctionDef) -> str:
		for decorator in fdef.decorator_list:
			if isinstance(decorator, ast.Name):
				if decorator.id == "classmethod": return "classmethod"
				elif decorator.id == "staticmethod": return "staticmethod"
			elif isinstance(decorator, ast.Attribute):
				if decorator.attr == "classmethod": return "classmethod"
				elif decorator.attr == "staticmethod": return "staticmethod"
		return ""

	@staticmethod
	def run_function(
		context: Context, 
		arguments: dict[str, NameTable], 
		function_table: DefinitionTable,
		call_stack: list
	) -> set[InstanceTable]:
		
		from typify.inferencing.executor import Executor
		
		tree = function_table.tree
		call_frame = CallFrameTable(f"frame@{function_table.parent.fqn}")
		call_frame.parent = function_table.parent

		for argname in arguments: 
			namespace_name = call_frame.get_name(argname)
			symbol_name = function_table.get_name(argname)
			for argdef in arguments[argname].definitions.values():
				ndef = DefinitionTable((argdef.module, argdef.position))
				ndef.points_to.update(argdef.points_to)
				namespace_name.new_def(ndef)
				symbol_name.merge_def(ndef)
		
		mod = call_frame.get_enclosing_module() 
		context.symbol_map[function_table] = call_frame
		context_meta = context.meta_map[mod]

		executor = Executor(
			context=context,
			module_meta=context_meta,
			symbol=function_table,
			namespace=call_frame, 
			call_stack=call_stack,
			tree=ast.Module(tree.body, type_ignores=[]), 
			snapshot_log=[]
		)

		returns = executor.execute()
		function_table.points_to.update(returns)
		return returns
	
	@staticmethod
	def map_call_arguments(
		call_node: ast.Call,
		parameters: dict[str, ParameterEntry],
		resolver: Resolver,
	) -> dict[str, NameTable]:

		resolved_args: dict[str, NameTable] = {}
		vararg_param = next((p for p in parameters.values() if p.is_vararg), None)

		positional_param_entries = [
			p for p in parameters.values()
			if not (p.is_vararg or p.is_kwarg or p.is_kwonly)
			and p.name not in {kw.arg for kw in call_node.keywords if kw.arg is not None}
		]

		for i, arg_node in enumerate(call_node.args[:len(positional_param_entries)]):
			param_entry = positional_param_entries[i]
			module = param_entry.nametable.get_latest_definition().module
			position = param_entry.nametable.get_latest_definition().position
			defkey = (module, position)

			new_namedef = DefinitionTable(defkey)

			for instance in resolver.resolve_value(arg_node):
				new_namedef.points_to.add(instance)

			name_copy = NameTable(param_entry.name)
			name_copy.new_def(new_namedef)
			resolved_args[param_entry.name] = name_copy

		extra_args = call_node.args[len(positional_param_entries):]

		if vararg_param and extra_args:
			store = []
			typeargs = []
			module = vararg_param.nametable.get_latest_definition().module
			position = vararg_param.nametable.get_latest_definition().position
			defkey = (module, position)
			for elt in extra_args:
				resolved = resolver.resolve_value(elt)
				unified = TypeUtils.unify([r.type_expr for r in resolved])
				typeargs.append(unified)
				store.append(resolved)

			instance = TypeUtils.instantiate(Builtins.get_type("tuple"), typeargs)
			instance.store = store

			new_namedef = DefinitionTable(defkey)
			new_namedef.points_to.add(instance)

			name_copy = NameTable(vararg_param.name)
			name_copy.new_def(new_namedef)
			resolved_args[vararg_param.name] = name_copy

		# Keyword arguments
		for kw in call_node.keywords:
			if kw.arg is None:
				continue
			if kw.arg in parameters:
				param_entry = parameters[kw.arg]
				module = param_entry.nametable.get_latest_definition().module
				position = param_entry.nametable.get_latest_definition().position
				defkey = (module, position)
				new_namedef = DefinitionTable(defkey)

				for instance in resolver.resolve_value(kw.value):
					new_namedef.points_to.add(instance)

				name_copy = NameTable(kw.arg)
				name_copy.new_def(new_namedef)
				resolved_args[kw.arg] = name_copy

		# Retain original param entries if not overridden
		for pname, param_entry in parameters.items():
			if pname not in resolved_args:
				resolved_args[pname] = param_entry.nametable

		return resolved_args


	#TODO: add support *varargs and **kwargs
	@staticmethod
	def collect_parameters(
		fdef: ast.FunctionDef,
		module_table: ModuleTable,
		resolver: Resolver
	) -> dict[str, ParameterEntry]:

		args_node = fdef.args
		parameters: dict[str, ParameterEntry] = {}

		def register_arg(
			arg: ast.arg,
			default_value: ast.expr = None,
			*,
			is_posonly=False,
			is_kwonly=False
		) -> ParameterEntry:
			name = arg.arg
			nametable = NameTable(name)
			position = (arg.lineno, arg.col_offset)
			defkey = (module_table, position)
			namedef = nametable.new_def(DefinitionTable(defkey))

			if default_value is not None:
				for instance in resolver.resolve_value(default_value):
					namedef.points_to.add(instance)

			entry = ParameterEntry(
				name=name,
				nametable=nametable,
				is_posonly=is_posonly,
				is_kwonly=is_kwonly,
			)
			parameters[name] = entry
			return entry

		# Positional-only args
		posonly_defaults = [None] * (len(args_node.posonlyargs) - len(args_node.defaults)) + args_node.defaults[:len(args_node.posonlyargs)]
		for arg, default in zip(args_node.posonlyargs, posonly_defaults):
			register_arg(arg, default, is_posonly=True)

		# Regular args
		regular_defaults = args_node.defaults[-len(args_node.args):] if args_node.defaults else []
		regular_defaults = [None] * (len(args_node.args) - len(regular_defaults)) + regular_defaults
		for arg, default in zip(args_node.args, regular_defaults):
			register_arg(arg, default)

		# *args
		if args_node.vararg:
			name = args_node.vararg.arg
			nametable = NameTable(name)
			position = (args_node.vararg.lineno, args_node.vararg.col_offset)
			defkey = (module_table, position)
			namedef = nametable.new_def(DefinitionTable(defkey))
			tuple_instance = TypeUtils.instantiate(Builtins.get_type("tuple"))
			namedef.points_to.add(tuple_instance)
			parameters[name] = ParameterEntry(
				name=name,
				nametable=nametable,
				is_vararg=True,
			)

		# Keyword-only args
		for arg, default in zip(args_node.kwonlyargs, args_node.kw_defaults):
			register_arg(arg, default, is_kwonly=True)

		# **kwargs
		if args_node.kwarg:
			name = args_node.kwarg.arg
			nametable = NameTable(name)
			position = (args_node.kwarg.lineno, args_node.kwarg.col_offset)
			defkey = (module_table, position)
			namedef = nametable.new_def(DefinitionTable(defkey))
			dict_expr = TypeExpr(Builtins.get_type("dict"), [TypeExpr(Builtins.get_type("str")), TypeExpr(Typing.get_type("Any"))])
			dict_instance = TypeUtils.instantiate_from_type_expr(dict_expr)
			namedef.points_to.update(dict_instance)
			parameters[name] = ParameterEntry(
				name=name,
				nametable=nametable,
				is_kwarg=True
			)

		return parameters



		
