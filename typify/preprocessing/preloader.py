import subprocess
import sys
import json

from pathlib import Path
from typing import Union
from dataclasses import dataclass

from typify.caching import GlobalCache
from typify.progbar import ProgressBar
from typify.preprocessing.dependency_utils import GraphBuilder
from typify.preprocessing.sequencer import Sequencer
from typify.preprocessing.core import GlobalContext

@dataclass
class SetupInfo:
	paths: list[Path]
	inference: dict[str, Path]

class Preloader:

	@staticmethod
	def _extract_current_env(python_executable=sys.executable) -> dict[str, Union[Path, list[Path]]]:
		script = """
import site, json

info = {
	"user_site_lib": site.getusersitepackages(),
	"site_libs": site.getsitepackages(),
}

print(json.dumps(info))
"""

		result = subprocess.run(
			[python_executable, "-c", script],
			capture_output=True,
			text=True,
			check=True
		)

		raw_info = json.loads(result.stdout)

		raw_info["user_site_lib"] = Path(Path(raw_info["user_site_lib"]))
		raw_info["site_libs"] = [Path(Path(p)) for p in raw_info["site_libs"]]

		return {
			"user_site_lib": raw_info["user_site_lib"],
			"site_libs": raw_info["site_libs"],
		}
	
	@staticmethod
	def load(
		cache_path: Path,
		clear_cache: bool,
		config: dict[str, Union[str, list[str], dict[str, str]]], 
		project_dir: Path,
	):
		from typify.preprocessing.precollector import PreCollector
		from typify.logging import logger

		paths = [project_dir]
		inference: dict[str, Path] = {}

		cenv = Preloader._extract_current_env()
		raw_paths = config.get("paths", [])

		for p in raw_paths:
			if p == "{auto}":
				for site in cenv.values():
					if isinstance(site, Path):
						paths.append(site)
					elif isinstance(site, list):
						paths.extend([s for s in site if isinstance(s, Path)])
			else:
				try:
					paths.append(Path(Path(p).resolve()))
				except Exception:
					continue

		for k, v in config.get("inference", {}).items():
			try:
				inference[k] = Path(v)
			except Exception:
				continue

		inference = {k: Path(v.resolve().as_posix()) for k, v in inference.items()}
		paths = [Path(p.resolve().as_posix()) for p in paths]

		logger.debug(f"{logger.emoji_map['libs']} [Preloader] Loading libraries for {len(paths)} path(s)")
		GlobalContext.libs = GlobalCache.setup(
			cache_path,
			clear_cache,
			paths
		)

		GlobalContext.path_index.clear()
		for lib in GlobalContext.libs.values():
			for apath, meta in lib.path_index.items():
				GlobalContext.path_index[apath.resolve()] = meta

		for k, v in inference.items():
			GlobalContext.inference[k] = GlobalContext.path_index.get(v.resolve())

		print()

		logger.debug(f"{logger.emoji_map['summary']} [Preloader] Building dependency graph (all libraries)", trail=1)
		GraphBuilder.build_graph_all(use_cache=True)

		project_lib = next(iter(GlobalContext.libs.values()))
		meta_values = list(project_lib.meta_map.values())
		progress = ProgressBar(len(meta_values), prefix="Collecting typeslots:")
		progress.display()

		for i, meta in enumerate(meta_values, 1):
			PreCollector(meta).visit(meta.tree)
			progress.update(i)
		
		logger.debug(f"{logger.emoji_map['ok']} [Preloader] Collected typeslots for {len(meta_values)} module(s)", trail=1)
