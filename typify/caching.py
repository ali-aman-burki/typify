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

@dataclass
class ModuleCache:
	tree: ast.Module
	trust_annotations: bool
	last_modified: float

	def to_meta(self, mpath: Path):
		from typify.preprocessing.module_meta import ModuleMeta
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

class GlobalCache:

	lib_structs: dict[Path, LibStruct] = {}
	libs_cache: dict[Path, LibraryCache] = {}
	global_index: dict[str, str] = {}
	cache_path: Path = None

	@staticmethod
	def get_cache_dir() -> Path:
		if sys.platform.startswith("win"):
			base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
		elif sys.platform == "darwin":
			base = Path.home() / "Library" / "Caches"
		else:
			base = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache"))

		target_path = base / "typify"
		return target_path


	@staticmethod
	def setup(config_paths: list[Path]) -> list["LibraryMeta"]:
		from typify.progbar import IndeterminateProgressBar
		cache_path = GlobalCache.get_cache_dir()
		GlobalCache.cache_path = cache_path
		cache_path.mkdir(parents=True, exist_ok=True)

		libs: list[LibraryMeta] = []

		global_index_file = cache_path / "index.json"
		if global_index_file.exists():
			with global_index_file.open("r", encoding="utf-8") as f:
				GlobalCache.global_index = json.load(f)
		else:
			GlobalCache.global_index = {}

		for lpath in config_paths:
			lib_id = None
			for key, existing in GlobalCache.global_index.items():
				if Path(existing) == lpath:
					lib_id = key
					break
			if lib_id is None:
				lib_id = str(len(GlobalCache.global_index))
				GlobalCache.global_index[lib_id] = lpath.as_posix()

			lib_dir = cache_path / lib_id
			lib_dir.mkdir(parents=True, exist_ok=True)

			lib_pickle = lib_dir / "library.pkl"

			snapshot = {
				str(p.relative_to(lpath)): p.stat().st_mtime
				for p in lpath.rglob("*")
				if p.suffix in {".py", ".pyi"}
			}
			digest = hashlib.sha1(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()

			progress_bar = IndeterminateProgressBar(
				prefix=f"Parsing modules in {Utils.last_n_parts(lpath, 2)}",
				suffix="Checking cache...",
			)
			progress_bar.start()

			if lib_pickle.exists():
				try:
					with open(lib_pickle, "rb") as f:
						cached: LibraryCache = pickle.load(f)
					if cached.digest == digest:
						GlobalCache.libs_cache[lpath] = cached
						libs.append(cached.meta)
						module_count = len(cached.meta.meta_map)
						progress_bar.set_suffix(f"Cached: {module_count} modules")
						progress_bar.done()
						continue
				except Exception:
					pass

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

			meta = LibraryMeta(lpath)
			meta.build(progress_bar=progress_bar)

			libcache = LibraryCache(
				lib_dir=lib_dir,
				lib_pickle=lib_pickle,
				digest=digest,
				meta=meta
			)
			with open(lib_pickle, "wb") as f:
				pickle.dump(libcache, f)

			GlobalCache.libs_cache[lpath] = libcache
			libs.append(meta)

			progress_bar.done()

		with global_index_file.open("w", encoding="utf-8") as f:
			json.dump(GlobalCache.global_index, f, indent=2)

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
			json.dump(libcache.index, f, indent=2)

		return new_mcache.to_meta(mpath)

	@staticmethod
	def prune():
		from hashlib import sha1

		def compute_digest(lpath: Path) -> str:
			snapshot = {
				str(p.relative_to(lpath)): p.stat().st_mtime
				for p in lpath.rglob("*")
				if p.suffix in {".py", ".pyi"}
			}
			return sha1(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()

		for lpath, libcache in list(GlobalCache.libs_cache.items()):
			if not lpath.exists():
				if libcache.lib_pickle.exists():
					libcache.lib_pickle.unlink()
				GlobalCache.libs_cache.pop(lpath, None)
				continue
			digest = compute_digest(lpath)
			if digest != libcache.digest:
				if libcache.lib_pickle.exists():
					libcache.lib_pickle.unlink()
				GlobalCache.libs_cache.pop(lpath, None)

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
				json.dump(libstruct.index, f, indent=2)

	@staticmethod
	def clear():
		cache_path = GlobalCache.get_cache_dir()

		if cache_path.exists():
			shutil.rmtree(cache_path, ignore_errors=True)

		GlobalCache.lib_structs.clear()
		GlobalCache.libs_cache.clear()
		GlobalCache.global_index.clear()
		GlobalCache.cache_path = None