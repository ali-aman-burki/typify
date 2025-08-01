import subprocess
import sys
import json

from pathlib import Path
from typing import Union
from dataclasses import dataclass

from typify.progbar import ProgressBar
from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.dependency_utils import GraphBuilder
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

		raw_info["user_site_lib"] = Path(raw_info["user_site_lib"])
		raw_info["site_libs"] = [Path(p) for p in raw_info["site_libs"]]

		return {
			"user_site_lib": raw_info["user_site_lib"],
			"site_libs": raw_info["site_libs"],
		}
	
	@staticmethod
	def load(config: dict[str, Union[str, list[str], dict[str, str]]], project_dir: Path):
		from typify.preprocessing.precollector import PreCollector

		paths = [project_dir]
		inference: dict[str, Path] = {}

		cenv = Preloader._extract_current_env()
		raw_paths = config.get("paths", [])

		for p in raw_paths:
			if p == "{CURRENT_ENV_SITES}":
				for site in cenv.values():
					if isinstance(site, Path):
						paths.append(site)
					elif isinstance(site, list):
						paths.extend([s for s in site if isinstance(s, Path)])
			else:
				try:
					paths.append(Path(p))
				except Exception:
					continue

		for k, v in config.get("inference", {}).items():
			try:
				inference[k] = Path(v)
			except Exception:
				continue

		GlobalContext.libs = [LibraryMeta(path) for path in paths]
		
		print()

		project_lib = GlobalContext.libs[0]
		meta_values = list(project_lib.meta_map.values())
		progress = ProgressBar(
			len(meta_values), 
			prefix=f"Collecting typeslots:", 
		)
		progress.display()

		for i, meta in enumerate(meta_values, 1):
			PreCollector(meta).visit(meta.tree)
			progress.update(i)
		
		for lib in GlobalContext.libs:
			for meta in lib.meta_map.values():
				for k, v in inference.items():
					try:
						if meta.src.resolve() == v.resolve() and k not in GlobalContext.inference:
							GlobalContext.inference[k] = meta
					except Exception:
						continue

				if GlobalContext.inference.keys() == inference.keys():
					break
		GraphBuilder.build_graph()
