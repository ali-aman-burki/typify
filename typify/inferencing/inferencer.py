from pathlib import Path
from collections import (
	deque, 
	defaultdict
)

from typify.caching import GlobalCache
from typify.logging import logger
from typify.progbar import ProgressBar
from typify.utils import Utils
from typify.preprocessing.module_meta import ModuleMeta
from typify.inferencing.commons import Builtins
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.executor import Executor
from typify.preprocessing.instance_utils import ReferenceSet
from typify.preprocessing.core import GlobalContext

class Inferencer:

	@staticmethod
	def process_sequence(
		sequence: list[ModuleMeta],
		reverse_deps: dict[ModuleMeta, set[ModuleMeta]],
		pass_counts: dict[str, int],
		processed: list[ModuleMeta],
		all_tracked_modules: set[ModuleMeta],
		shown_in_combined: set[ModuleMeta],
		progress: ProgressBar
	) -> None:

		is_single = len(sequence) == 1
		has_self_loop = (
			sequence[0] in GlobalContext.dependency_graph.get(sequence[0], set())
			if is_single else False
		)

		snapshots: dict[ModuleMeta, list[set]] = {meta: [] for meta in sequence}
		passes: dict[ModuleMeta, int] = {meta: 0 for meta in sequence}

		def run_pass(meta: ModuleMeta) -> list[set]:
			snapshot_log: list[ReferenceSet] = []
			GlobalContext.sysmodules.setdefault(
				meta.table.fqn,
				TypeUtils.instantiate_with_args(Builtins.get_type("module"))
			)
			GlobalContext.symbol_map[meta.table] = GlobalContext.sysmodules[meta.table.fqn]

			logger.info(f"{logger.emoji_map['types']} Inferring for {meta.table.fqn}")

			executor = Executor(
				module_meta=meta,
				symbol=meta.table,
				namespace=GlobalContext.sysmodules[meta.table.fqn],
				caller=None,
				arguments={},
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
				progress.update()
				shown_in_combined.add(meta)

			GlobalContext.sysmodules[meta.table.fqn].update_type_info(Builtins.get_type("module"))
			return

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

			GlobalContext.sysmodules[meta.table.fqn].update_type_info(Builtins.get_type("module"))
			processed.append(meta)

			if meta in all_tracked_modules and meta not in shown_in_combined:
				progress.update()
				shown_in_combined.add(meta)

		for meta in sequence:
			pass_counts[meta.table.fqn] = passes[meta]


	@staticmethod
	def infer(cache_path: Path) -> None:
		reverse_deps: dict[ModuleMeta, set[ModuleMeta]] = defaultdict(set)
		processed: list[ModuleMeta] = []
		pass_counts: dict[str, int] = {}
		corrected_sequences: list[list[ModuleMeta]] = []
		captured_metas: set[ModuleMeta] = set()

		project_only_modules: set[ModuleMeta] = set(GlobalContext.libs[0].meta_map.values())

		for src, targets in GlobalContext.dependency_graph.items():
			for tgt in targets:
				reverse_deps[tgt].add(src)

		for sequence in GlobalContext.sequences:
			if captured_metas == project_only_modules:
				break
			for meta in sequence:
				if meta in project_only_modules:
					captured_metas.add(meta)
			corrected_sequences.append(sequence)
		
		all_tracked_modules = {meta for seq in corrected_sequences for meta in seq}

		progress = ProgressBar(
			total=len(all_tracked_modules),
			prefix="Performing Inference:",
			progress_format="percent"
		)
		progress.display()
		shown_in_combined: set[ModuleMeta] = set()

		logger.debug("", header=False)
		logger.debug("Following Corrected Inference Sequences:")
		logger.debug("", header=False)
		
		pretty = Utils.pretty_list_arrow(corrected_sequences, columns=3)
		logger.debug(pretty, header=False)

		filtered_sequences = corrected_sequences.copy()

		for i in range(len(corrected_sequences), 0, -1):
			current = corrected_sequences[:i]
			context_id = repr(current)
			context_cache = GlobalCache.load_inference_context(context_id)
			if context_cache:
				# TODO: register cached context to global context
				filtered_sequences = corrected_sequences[i:]
				break

		for sequence in filtered_sequences:
			Inferencer.process_sequence(
				sequence,
				reverse_deps,
				pass_counts,
				processed,
				all_tracked_modules,
				shown_in_combined,
				progress
			)
			GlobalContext.processed_sequences.append(sequence)
			GlobalCache.cache_inference_context(cache_path)

		logger.info("Sequence Followed:", trail=1)
		sequence_output = [meta.table.fqn for meta in processed]
		
		pretty = Utils.pretty_list_arrow(sequence_output, columns=3)
		logger.info(pretty, header=False)
