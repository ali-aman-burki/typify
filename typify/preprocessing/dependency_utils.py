import ast
import json

from pathlib import Path

from typify.progbar import ProgressBar
from typify.preprocessing.instance_utils import Instance
from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.core import GlobalContext
from typify.preprocessing.sequencer import Sequencer
from typify.preprocessing.symbol_table import (
	Module, 
	Package
)

class DependencyUtils:

	@staticmethod
	def to_absolute_name(module_table: Module, name: str | None, level: int = 0) -> str:
		level = max(0, level)
		
		if level == 0:
			base_fqn = name or ""
		else:
			current_fqn = module_table.fqn
			parts = current_fqn.split(".")
			
			level = min(level, len(parts))
			base_parts = parts[:len(parts) - level]
			if name:
				base_parts.extend(name.split("."))
			base_fqn = ".".join(base_parts)
		
		return base_fqn

	@staticmethod
	def resolve_module_objects(
		defkey: tuple[Module, tuple[int, int]], 
		name: str | None, 
		level: int = 0
	) -> list[Instance]:

		fqn = DependencyUtils.to_absolute_name(defkey[0], name, level)
		for lib in GlobalContext.libs:
			if fqn in lib.fqn_map:
				chain = lib.fqn_map[fqn]

				if all(table.fqn in GlobalContext.sysmodules for table in chain):
					return [GlobalContext.sysmodules[table.fqn] for table in chain]

				modules = []

				if chain[0].fqn not in GlobalContext.sysmodules: break
				
				current_object = GlobalContext.sysmodules[chain[0].fqn]
				modules.append(current_object)

				for table in chain[1:]:
					if table.fqn in GlobalContext.sysmodules:
						current_object = GlobalContext.sysmodules[table.fqn]
						modules.append(current_object)

				return modules

		return []

class GraphBuilder:

	@staticmethod
	def initialize_globals():
		"""
		Merge library-level maps into GlobalContext once.
		"""
		from typify.logging import logger
		logger.debug(f"{logger.emoji_map['init']} [Deps] Initializing globals from libraries")
		for lib in GlobalContext.libs:
			GlobalContext.meta_map.update(lib.meta_map)
			GlobalContext.sysmodules.update(lib.sysmodules)

	@staticmethod
	def _dep_cache_file_for(lib) -> Path | None:
		from typify.caching import GlobalCache
		lcache = GlobalCache.libs_cache.get(lib.src)
		if lcache is None:
			return None
		return lcache.lib_dir / "deps.json"

	@staticmethod
	def _serialize_edges_for(lib) -> dict[str, list[str]]:
		edges: dict[str, list[str]] = {}
		lib_paths = {Path(m.src).resolve() for m in lib.meta_map.values()}

		for from_meta, tos in GlobalContext.dependency_graph.items():
			if Path(from_meta.src).resolve() not in lib_paths:
				continue
			from_key = Path(from_meta.src).resolve().as_posix()
			out: list[str] = []
			for to_meta in tos:
				if hasattr(to_meta, "src"):
					out.append(Path(to_meta.src).resolve().as_posix())
			edges[from_key] = sorted(set(out)) if out else []
		return edges

	@staticmethod
	def _load_edges_into_global(lib, edges: dict[str, list[str]]):
		builtins = GlobalContext.inference.get("builtins")
		for from_key, to_list in edges.items():
			from_meta = GlobalContext.path_index.get(Path(from_key).resolve())
			if not from_meta:
				continue
			out = set()
			if builtins:
				out.add(builtins)
			for to_key in to_list:
				to_meta = GlobalContext.path_index.get(Path(to_key).resolve())
				if to_meta:
					out.add(to_meta)
			GlobalContext.dependency_graph[from_meta] = out

	@staticmethod
	def _recompute_for_metas(metas: list["ModuleMeta"], progress: ProgressBar | None = None, log_files: bool = False):
		from typify.logging import logger
		builtins = GlobalContext.inference.get("builtins")
		total = len(metas)
		if total:
			logger.debug(f"{logger.emoji_map['patch']} [Deps] Recomputing {total} module(s)")
		for i, m in enumerate(metas, 1):
			GlobalContext.dependency_graph[m] = set()
			if builtins:
				GlobalContext.dependency_graph[m].add(builtins)
			DependencyTracker(m).visit(m.tree)
			if log_files:
				logger.debug(f"\t↳ {logger.emoji_map['file']} Recomputed {Path(m.src).resolve().as_posix()}")
			if progress is not None:
				progress.update(progress.iteration + 1)

	@staticmethod
	def build_graph_all(use_cache: bool = True):
		"""
		One progress bar whose total == total modules across all libraries.
		"""
		from typify.caching import GlobalCache
		from typify.logging import logger

		logger.debug(f"{logger.emoji_map['build']} [Deps] Starting dependency graph build")

		GlobalContext.meta_map.clear()
		GlobalContext.sysmodules.clear()
		GlobalContext.dependency_graph.clear()

		GraphBuilder.initialize_globals()

		plan: list[tuple[str, object, list["ModuleMeta"], int]] = []
		total_modules = 0

		for lib in GlobalContext.libs:
			dep_file = GraphBuilder._dep_cache_file_for(lib)
			modified = GlobalCache.modified_map.get(lib.src, set())
			lib_count = len(lib.meta_map)
			total_modules += lib_count

			if use_cache and dep_file and dep_file.exists() and not modified:
				plan.append(("load", lib, [], lib_count))
				continue

			if use_cache and dep_file and dep_file.exists() and modified:
				metas = []
				for abs_posix in modified:
					meta = GlobalContext.path_index.get(Path(abs_posix).resolve())
					if meta:
						metas.append(meta)
				plan.append(("patch", lib, metas, lib_count))
				continue

			metas = list(lib.meta_map.values())
			plan.append(("full", lib, metas, lib_count))

		progress = ProgressBar(total_modules, prefix="Building dependency graph:")
		progress.display()

		for action, lib, metas, lib_count in plan:
			dep_file = GraphBuilder._dep_cache_file_for(lib)
			lib_name = lib.src.resolve().as_posix()

			if action == "load":
				if dep_file and dep_file.exists():
					data = json.loads(dep_file.read_text(encoding="utf-8"))
					edges = data.get("edges", {})
					GraphBuilder._load_edges_into_global(lib, edges)
				progress.update(progress.iteration + lib_count)
				logger.debug(f"{logger.emoji_map['ok']} [Deps] Loaded {lib_count} module(s) from cache for {lib_name}")
				continue

			if action == "patch":
				if dep_file and dep_file.exists():
					data = json.loads(dep_file.read_text(encoding="utf-8"))
					edges = data.get("edges", {})
					GraphBuilder._load_edges_into_global(lib, edges)

				cached_count = lib_count - len(metas)
				if cached_count > 0:
					progress.update(progress.iteration + cached_count)
					logger.debug(f"{logger.emoji_map['changed']} [Deps] {cached_count} module(s) reused from cache in {lib_name}")

				# patched modules show indented lines
				GraphBuilder._recompute_for_metas(metas, progress=progress, log_files=True)

				if dep_file:
					new_edges = GraphBuilder._serialize_edges_for(lib)
					dep_file.write_text(json.dumps({
						"version": 1,
						"library_src": lib.src.resolve().as_posix(),
						"edges": new_edges
					}, indent="\t"), encoding="utf-8")
				logger.debug(f"{logger.emoji_map['patch']} [Deps] Patched {len(metas)} module(s) in {lib_name}")
				continue

			if action == "full":
				GraphBuilder._recompute_for_metas(metas, progress=progress, log_files=False)
				if dep_file:
					dep_file.write_text(json.dumps({
						"version": 1,
						"library_src": lib.src.resolve().as_posix(),
						"edges": GraphBuilder._serialize_edges_for(lib)
					}, indent="\t"), encoding="utf-8")
				logger.debug(f"{logger.emoji_map['libs']} [Deps] Fully rebuilt {lib_count} module(s) in {lib_name}")

		GlobalContext.sequences = Sequencer.generate_sequences(GlobalContext.dependency_graph)
		logger.debug(f"{logger.emoji_map['summary']} [Deps] Dependency graph build complete, sequences regenerated")

class DependencyTracker(ast.NodeVisitor):
	def __init__(self, module_meta: ModuleMeta):
		self.module_meta = module_meta
		self.module_table = module_meta.table
		self.in_function = 0

		GlobalContext.dependency_graph[self.module_meta] = {GlobalContext.inference["builtins"]}
	
	def as_module_metas(self, modules: list[Module]) -> set[ModuleMeta]:
		return {GlobalContext.meta_map[table] for table in modules if table in GlobalContext.meta_map}

	def filter_chain(self, chain: list[Module | Package]):
		result = []
		for table in chain:
			if isinstance(table, Package): result.append(table.modules["__init__"])
			else: result.append(table)
		return result

	def resolve_fqn_chain(self, name: str | None, level: int = 0) -> list[Module | Package]:
		base_fqn = DependencyUtils.to_absolute_name(self.module_table, name, level)

		for lib in GlobalContext.libs:
			if base_fqn in lib.fqn_map:
				chain = lib.fqn_map[base_fqn]
				metas = self.as_module_metas(self.filter_chain(chain))
				GlobalContext.dependency_graph[self.module_meta].update(metas)
				GlobalContext.dependency_graph[self.module_meta].discard(base_fqn)
				return chain

		return []

	def visit_Import(self, node):
		if self.in_function: return
		for alias in node.names: self.resolve_fqn_chain(alias.name)
		self.generic_visit(node)

	def visit_ImportFrom(self, node):
		if not self.in_function:
			names = {alias.name for alias in node.names if alias.name != "*"}
			chain = self.resolve_fqn_chain(node.module, node.level)
			if chain:
				endpoint = chain[-1]
				for name in names:
					if isinstance(endpoint, Package):
						if name in endpoint.packages: 
							self.resolve_fqn_chain(endpoint.packages[name].fqn)
						elif name in endpoint.modules: 
							self.resolve_fqn_chain(endpoint.modules[name].fqn)
				
		self.generic_visit(node)
	
	def visit_FunctionDef(self, node):
		self.in_function += 1
		self.generic_visit(node)
		self.in_function -= 1