import subprocess
import sys
import json
import re

from pathlib import Path
from typing import Union
from dataclasses import dataclass

from src.preprocessing.library_meta import LibraryMeta
from src.preprocessing.dependency_utils import GraphBuilder, DependencyBundle
from src.preprocessing.symbol_slot_collector import SymbolSlotCollector
from src.inferencing.commons import bind

@dataclass
class TypifyPaths:
	preload: dict[str, Path]
	ondemand: dict[str, Path]

class Preloader:

	@staticmethod
	def extract_current_env(python_executable=sys.executable) -> dict[str, Union[str, Path, list[Path]]]:
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

		return {
			"user_site_lib": raw_info["user_site_lib"],
			"site_libs": raw_info["site_libs"],
		}
	
	@staticmethod
	def get_paths(config: dict[str, Union[str, dict[str, str]]]) -> TypifyPaths:
		defaults = Preloader.extract_current_env()
		config.setdefault("preload", "")
		config.setdefault("ondemand", "CURRENT_ENV")
		paths_dict: dict[str, str] = config.get("paths", {})

		for key, value in paths_dict.items():
			config["preload"] = config["preload"].replace(f"{{{key}}}", value)
			config["ondemand"] = config["ondemand"].replace(f"{{{key}}}", value)

		project_dir = Path(config["project_dir"]).resolve()

		def resolve_paths(raw: str) -> dict[str, Path]:
			result = {}
			for p in re.split(r"\s*,\s*", raw):
				if not p:
					continue
				resolved = Path(p).resolve()
				label = next((k for k, v in paths_dict.items() if v == p), resolved.name)
				result[label] = resolved
			return result

		preload_raw = config["preload"]
		preload_paths = resolve_paths(preload_raw)
		preload_paths = {project_dir.name: project_dir, **{k: p for k, p in preload_paths.items() if p != project_dir}}

		ondemand_raw = config["ondemand"].strip()
		if not ondemand_raw:
			ondemand_paths = {}
		elif ondemand_raw == "CURRENT_ENV":
			ondemand_paths = {
				"user_site_lib": Path(defaults["user_site_lib"]).resolve(),
				**{f"site_lib_{i}": Path(p).resolve() for i, p in enumerate(defaults["site_libs"])}
			}
		else:
			ondemand_paths = resolve_paths(ondemand_raw)

		return TypifyPaths(preload_paths, ondemand_paths)

	@staticmethod
	def load(config) -> DependencyBundle:
		paths = Preloader.get_paths(config)
		libs: dict[str, LibraryMeta] = {
			label: LibraryMeta(preload_path) for label, preload_path in paths.preload.items()
		}

		bundle = GraphBuilder.build_graph(libs)

		for libmeta in libs.values():
			for modmeta in libmeta.meta_map.values():
				SymbolSlotCollector(modmeta).visit(modmeta.tree)

		bind(libs)
		return bundle