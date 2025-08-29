from pathlib import Path
from collections import (
	deque, 
	defaultdict
)

from typify.logging import logger
from typify.progbar import ProgressBar
from typify.utils import Utils
from typify.caching import GlobalCache
from typify.preprocessing.module_meta import ModuleMeta
from typify.inferencing.commons import Builtins
from typify.inferencing.typeutils import TypeUtils
from typify.inferencing.executor import Executor
from typify.preprocessing.instance_utils import ReferenceSet
from typify.preprocessing.core import GlobalContext
from typify.preprocessing.sequencer import Sequencer

class Inferencer:

	@staticmethod
	def process_sequence(
		sequence: list[ModuleMeta],
		reverse_deps: dict[ModuleMeta, list[ModuleMeta]],
		sequence_followed: list[ModuleMeta]
	) -> None:

		is_single = len(sequence) == 1
		has_self_loop = (
			sequence[0] in GlobalContext.dependency_graph.get(sequence[0], [])
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

			logger.debug(f"{logger.emoji_map['types']} Inferring for {meta.table.fqn}")

			executor = Executor(
				module_meta=meta,
				symbol=meta.table,
				namespace=GlobalContext.sysmodules[meta.table.fqn],
				caller=None,
				arguments={},
				tree=meta.tree,
				snapshot_log=snapshot_log
			)
			sequence_followed.append(meta)
			executor.execute()
			return executor.snapshot()

		if is_single and not has_self_loop:
			meta = sequence[0]
			new_snapshot = run_pass(meta)
			snapshots[meta] = new_snapshot

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
				for dependent in reverse_deps.get(meta, []):
					if dependent in sequence and dependent not in in_worklist:
						worklist.append(dependent)
						in_worklist.add(dependent)

			GlobalContext.sysmodules[meta.table.fqn].update_type_info(Builtins.get_type("module"))

	@staticmethod
	def _init_structures():
		reverse_deps: dict[ModuleMeta, list[ModuleMeta]] = defaultdict(list)
		corrected_sequences: list[list[ModuleMeta]] = []
		captured_metas: set[ModuleMeta] = set()

		sequences = Sequencer.generate_sequences(GlobalContext.dependency_graph)

		project_libpath = next(iter(GlobalContext.libs.keys()))
		project_only_modules: set[ModuleMeta] = set(GlobalContext.libs[project_libpath].meta_map.values())

		for src, targets in GlobalContext.dependency_graph.items():
			for tgt in targets:
				reverse_deps[tgt].append(src)

		for sequence in sequences:
			if captured_metas == project_only_modules:
				break
			for meta in sequence:
				if meta in project_only_modules:
					captured_metas.add(meta)
			corrected_sequences.append(sequence)
		
		return reverse_deps, corrected_sequences

	@staticmethod
	def infer(dont_cache: bool):
		reverse_deps, corrected_sequences = Inferencer._init_structures()
		project_libpath = next(iter(GlobalContext.libs.keys()))

		progress = ProgressBar(
			total=len(corrected_sequences),
			prefix="Performing Inference",
			progress_format="percent"
		)
		progress.display()
		
		logger.debug("", header=False)
		logger.debug(f"{logger.emoji_map['search']} {len(corrected_sequences)} total sequences to process")
		logger.debug("", header=False)
		
		pretty = Utils.pretty_list_arrow(corrected_sequences, columns=3)
		logger.debug(pretty, header=False)
		
		rebuilt_libs = GlobalCache.rebuilt_libs
		filter_1: list[list[ModuleMeta]] = []
		
		for i in range(len(corrected_sequences), 0, -1):
			current_path = corrected_sequences[:i]
			flat = {mod for sublist in current_path for mod in sublist}
			matching_libs = {
				k
				for k, lib in GlobalContext.libs.items()
				if flat.intersection(lib.meta_map.values())
			}
			contains_rebuilt = matching_libs.intersection(rebuilt_libs)
			if not contains_rebuilt:
				modified = False
				for ml in matching_libs:
					search_space = GlobalCache.modified_map.get(ml, set())
					if any(f.src.resolve().as_posix() in search_space for f in flat):
						modified = True
						break
				if not modified:
					filter_1 = current_path
					break
		
		remaining = corrected_sequences.copy()
		processed_sequences: list[list[ModuleMeta]] = []
		sequence_followed: list[ModuleMeta] = []

		logger.debug(f"{logger.emoji_map['search']} Checking cache for contexts.")
		for i in range(len(filter_1), 0, -1):
			current_path = filter_1[:i]
			context_id = repr(current_path)
			sequence_followed = GlobalCache.load_inference_context(context_id)
			if sequence_followed:
				logger.debug(f"{logger.emoji_map['ok']} [Cache] Cache hit for {i} sequences (restored {len(set(sequence_followed))} module(s))")
				new_graph = {}
				for meta, deps in GlobalContext.dependency_graph.items():
					new_meta = GlobalContext.path_index.get(meta.src, meta)
					new_deps = [GlobalContext.path_index.get(d.src, d) for d in deps]
					new_graph[new_meta] = new_deps
				GlobalContext.dependency_graph = new_graph

				reverse_deps, corrected_sequences = Inferencer._init_structures()
				remaining = corrected_sequences[i:]
				processed_sequences = corrected_sequences[:i]
				progress.update(i)
				break
		
		if not remaining:
			logger.debug(f"{logger.emoji_map['ok']} [Cache] Full cached context restored. Inference Skipped.")
		elif remaining and sequence_followed:
			logger.debug(f"{logger.emoji_map['ok']} [Cache] Partial cached context restored. Remaining Inference Started.")
		elif not sequence_followed: 
			logger.debug(f"{logger.emoji_map['refresh']} [Cache] No cached context found. Recomputing Inference.")

		logger.debug("", header=False)

		for sequence in remaining:
			Inferencer.process_sequence(
				sequence,
				reverse_deps,
				sequence_followed
			)
			processed_sequences.append(sequence)

			current_path = processed_sequences
			flat = {mod for sublist in current_path for mod in sublist}

			libs = {
				k: lib
				for k, lib in GlobalContext.libs.items()
				if flat.intersection(lib.meta_map.values())
			}

			if not (dont_cache and project_libpath in libs):
				GlobalCache.stage_inference_context(
					libs,
					processed_sequences,
					sequence_followed
				)
			progress.update()
				
		if remaining: logger.debug("", header=False)

		logger.debug("Sequence Followed:")
		sequence_followed = [meta.table.fqn for meta in sequence_followed]
		
		pretty = Utils.pretty_list_arrow(sequence_followed, columns=3)
		logger.debug(pretty, header=False)

		logger.info(f"{logger.emoji_map['ok']} Inference complete: "
			f"{len(processed_sequences)} sequences processed "
			f"({len(set(sequence_followed))} module(s) in total)")