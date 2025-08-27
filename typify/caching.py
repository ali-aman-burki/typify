import ast
import pickle
import json
import hashlib
import os
import sys
import shutil

from pathlib import Path
from dataclasses import dataclass

from typify.utils import Utils
from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.instance_utils import Instance
from typify.inferencing.call_stack import CallStack
from typify.preprocessing.symbol_table import (
	Module,
	ClassDefinition,
	FunctionDefinition,
	CallFrame
)

@dataclass
class ModuleCache:
	tree: ast.Module
	trust_annotations: bool
	last_modified: float

	def to_meta(self, mpath: Path):
		return ModuleMeta(
			mpath,
			self.tree,
			self.trust_annotations
		)

@dataclass
class LibStruct:
	path: Path
	mods: dict[Path, Path]
	index: dict[str, str]

@dataclass
class LibraryCache:
	lib_dir: Path
	lib_pickle: Path
	digest: str
	meta: LibraryMeta
	snapshot: dict[str, float] 

#ignore for now
@dataclass
class InferenceCache:
	call_stack: CallStack
	sysmodules: dict[str, ModuleMeta]
	symbol_map: dict[Module | ClassDefinition | FunctionDefinition, Instance | CallFrame]
	function_object_map: dict[FunctionDefinition, Instance]
	meta_map: dict[Module, ModuleMeta]
	singletons: dict[str, Instance]

class GlobalCache:

	lib_structs: dict[Path, LibStruct] = {}
	libs_cache: dict[Path, LibraryCache] = {}
	global_index: dict[str, str] = {}
	modified_map: dict[Path, set[str]] = {}

	@staticmethod
	def get_system_cache() -> Path:
		if sys.platform.startswith("win"):
			base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
		elif sys.platform == "darwin":
			base = Path.home() / "Library" / "Caches"
		else:
			base = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache"))

		target_path = base / "typify"
		return target_path

	#ignore for now
	@staticmethod
	def save_inference_context(cache_path: Path):
		from typify.preprocessing.core import GlobalContext

		cache_path.mkdir(parents=True, exist_ok=True)

		context_id = repr(GlobalContext.processed_sequences)

		inference_cache = InferenceCache(
			call_stack=GlobalContext.call_stack,
			sysmodules=GlobalContext.sysmodules,
			symbol_map=GlobalContext.symbol_map,
			function_object_map=GlobalContext.function_object_map,
			meta_map=GlobalContext.meta_map,
			singletons=GlobalContext.singletons
		)

	@staticmethod
	def compute_snapshot(lpath: Path) -> dict[str, float]:
		return {
			p.relative_to(lpath).as_posix(): p.stat().st_mtime
			for p in lpath.rglob("*")
			if p.suffix in {".py", ".pyi"}
		}

	@staticmethod
	def setup(
		cache_path: Path,
		clear_cache: bool, 
		config_paths: list[Path]
	) -> list[LibraryMeta]:
		from typify.progbar import IndeterminateProgressBar
		from typify.logging import logger

		cache_path.mkdir(parents=True, exist_ok=True)

		if clear_cache: GlobalCache.clear(cache_path)

		libs: list[LibraryMeta] = []

		global_index_file = cache_path / "index.json"
		if global_index_file.exists():
			with global_index_file.open("r", encoding="utf-8") as f:
				GlobalCache.global_index = json.load(f)
		else:
			GlobalCache.global_index = {}

		for lpath in config_paths:
			lpath_str = lpath.as_posix()
			lib_id = GlobalCache.global_index.get(lpath_str)
			if lib_id is None:
				lib_id = str(len(GlobalCache.global_index))
				GlobalCache.global_index[lpath_str] = lib_id

			lib_dir = cache_path / lib_id
			lib_dir.mkdir(parents=True, exist_ok=True)

			lib_pickle = lib_dir / "library.pkl"

			snapshot = GlobalCache.compute_snapshot(lpath)
			digest = hashlib.sha1(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()

			progress_bar = IndeterminateProgressBar(
				prefix=f"Locating modules in {Utils.last_n_parts(lpath, 2)}",
				suffix="Checking cache",
			)
			progress_bar.start()

			cached: LibraryCache | None = None
			if lib_pickle.exists():
				try:
					with open(lib_pickle, "rb") as f:
						cached = pickle.load(f)
					if cached.digest == digest:
						GlobalCache.libs_cache[lpath] = cached
						libs.append(cached.meta)
						module_count = len(cached.meta.meta_map)
						progress_bar.set_suffix(f"Cached: {module_count} modules")
						logger.debug(f"{logger.emoji_map['ok']} [Cache] {lpath.as_posix()}")
						logger.debug(f"\tReused {module_count} modules (cache hit)")
						GlobalCache.modified_map[lpath] = set()
						progress_bar.done()
						continue
				except Exception as e:
					logger.debug(f"{logger.emoji_map['warn']} [Cache] {lpath.as_posix()}")
					logger.debug(f"\tCorrupted cache pickle, forcing rebuild ({e})")
					cached = None

			index_file = lib_dir / "index.json"
			if index_file.exists():
				with index_file.open("r", encoding="utf-8") as f:
					index = json.load(f)
			else:
				index = {}
			mods: dict[Path, Path] = {}
			for key, original in index.items():
				fpath = lib_dir / f"{key}.pkl"
				if fpath.exists():
					mods[Path(original)] = fpath
			GlobalCache.lib_structs[lpath] = LibStruct(lib_dir, mods, index)

			if cached is not None and isinstance(cached.meta, LibraryMeta):
				old_snapshot = cached.snapshot or {}
				old_paths = set(old_snapshot.keys())
				new_paths = set(snapshot.keys())

				added   = new_paths - old_paths
				removed = old_paths - new_paths
				common  = new_paths & old_paths
				modified = {p for p in common if snapshot[p] != old_snapshot[p]}

				if not added and not removed:
					meta = cached.meta
					module_count = len(meta.meta_map)
					logger.debug(f"{logger.emoji_map['patch']} [Cache] {lpath.as_posix()}")
					logger.debug(f"\tIncremental refresh: {len(modified)} trees updated")
					logger.debug(f"\tTotal modules: {module_count}")

					abs_posix_modified = {(lpath / rel).resolve().as_posix() for rel in modified}
					GlobalCache.modified_map[lpath] = abs_posix_modified

					for rel in sorted(modified):
						abspath = (lpath / rel).resolve()
						existing = meta.get_meta_by_path(abspath)
						if existing is None:
							logger.debug(f"\t\t↳ {logger.emoji_map['warn']} Skipping {rel}, not found in meta")
							continue

						refreshed = GlobalCache.get_module_meta(
							lpath,
							abspath,
							existing.trust_annotations
						)
						existing.tree = refreshed.tree
						existing.trust_annotations = refreshed.trust_annotations
						logger.debug(f"\t\t↳ {logger.emoji_map['file']} Updated tree for {rel}")

					libcache = LibraryCache(
						lib_dir=lib_dir,
						lib_pickle=lib_pickle,
						digest=digest,
						meta=meta,
						snapshot=snapshot,
					)
					with open(lib_pickle, "wb") as f:
						pickle.dump(libcache, f)

					GlobalCache.libs_cache[lpath] = libcache
					libs.append(meta)
					progress_bar.set_suffix(f"Cached: {module_count} modules")
					progress_bar.done()
					continue

			meta = LibraryMeta(lpath)
			meta.build(progress_bar=progress_bar)
			module_count = len(meta.meta_map)
			logger.debug(f"{logger.emoji_map['build']} [Cache] {lpath.as_posix()}")
			logger.debug(f"\tFull rebuild performed")
			logger.debug(f"\tTotal modules: {module_count}")

			GlobalCache.modified_map[lpath] = set()

			libcache = LibraryCache(
				lib_dir=lib_dir,
				lib_pickle=lib_pickle,
				digest=digest,
				meta=meta,
				snapshot=snapshot,
			)
			with open(lib_pickle, "wb") as f:
				pickle.dump(libcache, f)

			GlobalCache.libs_cache[lpath] = libcache
			libs.append(meta)

		with global_index_file.open("w", encoding="utf-8") as f:
			json.dump(GlobalCache.global_index, f, indent='\t')

		total_modules = sum(len(meta.meta_map) for meta in libs)
		logger.debug(f"{logger.emoji_map['ok']} [Cache Summary]")
		logger.debug(f"\tLibraries processed: {len(libs)}")
		logger.debug(f"\tTotal modules: {total_modules}")

		return libs

	@staticmethod
	def get_module_meta(lpath: Path, mpath: Path, trust_annotations: bool):
		libcache = GlobalCache.lib_structs[lpath]

		pickled = libcache.mods.get(mpath)
		if pickled and pickled.exists():
			with open(pickled, "rb") as f:
				mcache: ModuleCache = pickle.load(f)
				if mcache.last_modified == mpath.stat().st_mtime:
					return mcache.to_meta(mpath)

		new_mcache = ModuleCache(
			Utils.load_tree(mpath),
			trust_annotations,
			mpath.stat().st_mtime
		)

		if mpath in libcache.mods:
			fname = pickled.stem
		else:
			fname = str(len(libcache.index))
		pickled_path = libcache.path / f"{fname}.pkl"

		with open(pickled_path, "wb") as wf:
			pickle.dump(new_mcache, wf)

		libcache.mods[mpath] = pickled_path
		libcache.index[fname] = mpath.as_posix()

		index_file = libcache.path / "index.json"
		with index_file.open("w", encoding="utf-8") as f:
			json.dump(libcache.index, f, indent='\t')

		return new_mcache.to_meta(mpath)

	@staticmethod
	def prune():
		from hashlib import sha1

		def compute_digest(lpath: Path) -> str:
			snapshot = {
				p.relative_to(lpath).as_posix(): p.stat().st_mtime
				for p in lpath.rglob("*")
				if p.suffix in {".py", ".pyi"}
			}
			return sha1(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()

		dead_libs: set[str] = set()

		for lpath, libcache in list(GlobalCache.libs_cache.items()):
			if not lpath.exists():
				if libcache.lib_pickle.exists():
					libcache.lib_pickle.unlink()
				GlobalCache.libs_cache.pop(lpath, None)
				dead_libs.add(lpath.as_posix())
				continue

			digest = compute_digest(lpath)
			if digest != libcache.digest:
				if libcache.lib_pickle.exists():
					libcache.lib_pickle.unlink()
				GlobalCache.libs_cache.pop(lpath, None)
				dead_libs.add(lpath.as_posix())

		for _, libstruct in GlobalCache.lib_structs.items():
			to_remove = []
			for key, mpath in libstruct.index.items():
				if not Path(mpath).exists():
					to_remove.append(key)
			for key in to_remove:
				libstruct.index.pop(key, None)
				fpath = libstruct.path / f"{key}.pkl"
				if fpath.exists():
					fpath.unlink()

			valid = set(libstruct.index.keys())
			for file in libstruct.path.glob("*.pkl"):
				if file.stem not in valid:
					file.unlink()

			mods: dict[Path, Path] = {}
			for key, original in libstruct.index.items():
				fpath = libstruct.path / f"{key}.pkl"
				if fpath.exists():
					mods[Path(original)] = fpath
			libstruct.mods = mods

			index_file = libstruct.path / "index.json"
			with index_file.open("w", encoding="utf-8") as f:
				json.dump(libstruct.index, f, indent='\t')

		if dead_libs:
			to_delete = [path for path in GlobalCache.global_index if path in dead_libs]
			for path in to_delete:
				GlobalCache.global_index.pop(path, None)

			global_index_file = GlobalCache.get_system_cache() / "index.json"
			if global_index_file.exists():
				with global_index_file.open("w", encoding="utf-8") as f:
					json.dump(GlobalCache.global_index, f, indent='\t')

	@staticmethod
	def clear(cache_path: Path):
		if cache_path.exists():
			shutil.rmtree(cache_path, ignore_errors=True)

		GlobalCache.lib_structs.clear()
		GlobalCache.libs_cache.clear()
		GlobalCache.global_index.clear()