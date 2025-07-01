from collections import deque, defaultdict

from typify.preprocessing.dependency_utils import DependencyBundle
from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.symbol_table import InstanceTable, ModuleTable
from typify.inferencing.commons import Builtins
from typify.inferencing.typeutils import TypeUtils, TypeExpr
from typify.inferencing.executor import Context, Executor

class Inferencer:

	@staticmethod
	def infer(bundle: DependencyBundle) -> None:
		meta_map: dict[ModuleTable, ModuleMeta] = bundle.meta_map
		sequences: list[list[ModuleMeta]] = bundle.sequences
		sysmodules: dict[str, InstanceTable] = bundle.sysmodules
		libs = bundle.libs
		cleaned_graph: dict[ModuleMeta, set[ModuleMeta]] = bundle.cleaned_graph

		context_map: dict[ModuleMeta, Context] = {
			meta: Context(meta, libs, sysmodules, {}, meta_map)
			for meta in meta_map.values()
		}
		reverse_deps: dict[ModuleMeta, set[ModuleMeta]] = defaultdict(set)
		processed: list[ModuleMeta] = []
		pass_counts: dict[str, int] = {}

		for src, targets in cleaned_graph.items():
			for tgt in targets:
				reverse_deps[tgt].add(src)

		for sequence in sequences:
			is_single = len(sequence) == 1
			has_self_loop = (
				sequence[0] in cleaned_graph.get(sequence[0], set())
				if is_single else False
			)

			snapshots: dict[ModuleMeta, list[set[str]]] = {meta: [] for meta in sequence}
			passes: dict[ModuleMeta, int] = {meta: 0 for meta in sequence}

			def run_pass(meta: ModuleMeta) -> list[set[str]]:
				snapshot_log: list[set[InstanceTable]] = []
				sysmodules.setdefault(
					meta.table.fqn,
					TypeUtils.instantiate(Builtins.get_type("module"))
				)
				context_map[meta].symbol_map[meta.table] = sysmodules[meta.table.fqn]
				executor = Executor(
					context=context_map[meta],
					symbol=meta.table,
					namespace=sysmodules[meta.table.fqn],
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

		print("\nSequence Followed:")
		print(" -> ".join(meta.table.fqn for meta in processed))
