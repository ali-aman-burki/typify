from collections import (
    deque, 
    defaultdict
)

from typify.logging import logger
from typify.progbar import ProgressBar
from typify.utils import Utils
from typify.preprocessing.module_meta import ModuleMeta
from typify.inferencing.commons import Builtins
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.executor import Executor
from typify.inferencing.call_stack import CallStack
from typify.preprocessing.instance_utils import ReferenceSet
from typify.preprocessing.core import GlobalContext

class Inferencer:

	@staticmethod
	def infer() -> None:

		sequences = GlobalContext.sequences
		sysmodules = GlobalContext.sysmodules
		libs = GlobalContext.libs
		cleaned_graph = GlobalContext.cleaned_graph

		call_stack = CallStack()

		reverse_deps: dict[ModuleMeta, set[ModuleMeta]] = defaultdict(set)
		processed: list[ModuleMeta] = []
		pass_counts: dict[str, int] = {}

		project_only_modules: set[ModuleMeta] = set(libs[0].meta_map.values())
		inference_only_modules: set[ModuleMeta] = set(GlobalContext.inference.values())
		all_tracked_modules: set[ModuleMeta] = project_only_modules | inference_only_modules

		combined_progress = ProgressBar(
			total=len(all_tracked_modules),
			prefix="Performing Inference:",
			progress_format="percent"
		)
		combined_progress.display()
		shown_in_combined: set[ModuleMeta] = set()

		for src, targets in cleaned_graph.items():
			for tgt in targets:
				reverse_deps[tgt].add(src)

		logger.debug("", header=False)

		for sequence in sequences:
			if all_tracked_modules.issubset(shown_in_combined):
				if not any(meta in all_tracked_modules for meta in sequence):
					continue

			is_single = len(sequence) == 1
			has_self_loop = (
				sequence[0] in cleaned_graph.get(sequence[0], set())
				if is_single else False
			)

			snapshots: dict[ModuleMeta, list[set]] = {meta: [] for meta in sequence}
			passes: dict[ModuleMeta, int] = {meta: 0 for meta in sequence}

			def run_pass(meta: ModuleMeta) -> list[set]:
				snapshot_log: list[ReferenceSet] = []
				sysmodules.setdefault(
					meta.table.fqn,
					TypeUtils.instantiate_with_args(Builtins.get_type("module"))
				)
				GlobalContext.symbol_map[meta.table] = sysmodules[meta.table.fqn]
				executor = Executor(
					module_meta=meta,
					symbol=meta.table,
					namespace=sysmodules[meta.table.fqn],
					caller=None,
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

				if meta in all_tracked_modules and meta not in shown_in_combined:
					combined_progress.update()
					shown_in_combined.add(meta)

				sysmodules[meta.table.fqn].update_type_info(Builtins.get_type("module"))
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

				sysmodules[meta.table.fqn].update_type_info(Builtins.get_type("module"))
				processed.append(meta)

				if meta in all_tracked_modules and meta not in shown_in_combined:
					combined_progress.update()
					shown_in_combined.add(meta)

			for meta in sequence:
				pass_counts[meta.table.fqn] = passes[meta]

		logger.info("Sequence Followed:", trail=1)
		sequence_output = [meta.table.fqn for meta in processed]
		
		pretty = Utils.pretty_list_arrow(sequence_output, columns=3)
		logger.info(pretty, header=False)
