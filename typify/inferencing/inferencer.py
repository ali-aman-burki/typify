from collections import deque, defaultdict

from typify.logging import logger
from typify.preprocessing.dependency_utils import DependencyBundle
from typify.preprocessing.module_meta import ModuleMeta
from typify.inferencing.commons import Builtins
from typify.inferencing.typeutils import TypeUtils, TypeExpr
from typify.inferencing.executor import Context, Executor
from typify.inferencing.call_stack import CallStack
from typify.preprocessing.symbol_table import (
    ReferenceSet, 
    Instance, 
    Module
)

class Inferencer:

	@staticmethod
	def infer(bundle: DependencyBundle) -> None:
		meta_map: dict[Module, ModuleMeta] = bundle.meta_map
		sequences: list[list[ModuleMeta]] = bundle.sequences
		sysmodules: dict[str, Instance] = bundle.sysmodules
		libs = bundle.libs
		cleaned_graph: dict[ModuleMeta, set[ModuleMeta]] = bundle.cleaned_graph

		context = Context(libs, sysmodules, {}, meta_map)
		call_stack = CallStack()

		reverse_deps: dict[ModuleMeta, set[ModuleMeta]] = defaultdict(set)
		processed: list[ModuleMeta] = []
		pass_counts: dict[str, int] = {}

		for src, targets in cleaned_graph.items():
			for tgt in targets:
				reverse_deps[tgt].add(src)

		logger.debug("", header=False)

		for sequence in sequences:
			is_single = len(sequence) == 1
			has_self_loop = (
				sequence[0] in cleaned_graph.get(sequence[0], set())
				if is_single else False
			)

			snapshots: dict[ModuleMeta, list[set[str]]] = {meta: [] for meta in sequence}
			passes: dict[ModuleMeta, int] = {meta: 0 for meta in sequence}

			def run_pass(meta: ModuleMeta) -> list[set[str]]:
				snapshot_log: list[ReferenceSet] = []
				sysmodules.setdefault(
					meta.table.fqn,
					TypeUtils.instantiate(Builtins.get_type("module"))
				)
				context.symbol_map[meta.table] = sysmodules[meta.table.fqn]
				executor = Executor(
					context=context,
					module_meta=meta,
					symbol=meta.table,
					namespace=sysmodules[meta.table.fqn],
					arguments={},
					call_stack=call_stack,
					tree=meta.tree,
					snapshot_log=snapshot_log
				)
				executor.execute()
				return executor.snapshot()

			if is_single and not has_self_loop:
				meta = sequence[0]
				new_snapshot = run_pass(meta)
				snapshots[meta] = new_snapshot
				pass_counts[meta.table.fqn] = 1
				processed.append(meta)
				sysmodules[meta.table.fqn].type_expr = TypeExpr(Builtins.get_type("module"))
				continue

			worklist: deque[ModuleMeta] = deque(sequence)
			in_worklist: set[ModuleMeta] = set(sequence)

			while worklist:
				meta = worklist.popleft()
				in_worklist.remove(meta)
				passes[meta] += 1

				new_snapshot = run_pass(meta)
				if new_snapshot != snapshots[meta]:
					snapshots[meta] = new_snapshot

					for dependent in reverse_deps.get(meta, set()):
						if dependent in sequence and dependent not in in_worklist:
							worklist.append(dependent)
							in_worklist.add(dependent)

				sysmodules[meta.table.fqn].type_expr = TypeExpr(Builtins.get_type("module"))
				processed.append(meta)

			for meta in sequence:
				pass_counts[meta.table.fqn] = passes[meta]

		logger.debug("Sequence Followed:", trail=1)
		logger.debug(" -> ".join(meta.table.fqn for meta in processed))
