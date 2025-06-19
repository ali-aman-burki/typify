import subprocess, sys, json, re

from pathlib import Path
from typing import Union

from src.preloading.commons import TypifyPaths

class SetupUtils:

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
	def get_paths(config_path: Path) -> TypifyPaths:
		defaults = SetupUtils.extract_current_env()

		with open(config_path, "r") as f:
			config: dict[str, Union[str, dict[str, str]]] = json.load(f)

		config.setdefault("preload", "")
		config.setdefault("ondemand", "CURRENT_ENV")

		paths_dict: dict[str, str] = config.get("paths", {})
		for key, value in paths_dict.items():
			config["preload"] = config["preload"].replace(f"{{{key}}}", value)
			config["ondemand"] = config["ondemand"].replace(f"{{{key}}}", value)

		preload_paths = [Path(p).resolve() for p in re.split(r"\s*,\s*", config["preload"]) if p]

		ondemand_raw = config["ondemand"].strip()
		if not ondemand_raw:
			ondemand_paths = []
		elif ondemand_raw == "CURRENT_ENV":
			ondemand_paths = [Path(defaults["user_site_lib"]).resolve()] + [
				Path(p).resolve() for p in defaults["site_libs"]
			]
		else:
			ondemand_paths = [Path(p).resolve() for p in re.split(r"\s*,\s*", ondemand_raw) if p]

		return TypifyPaths(preload_paths, ondemand_paths)

	@staticmethod
	def preprocess_libs(config_path: Path): 
		paths = SetupUtils.get_paths(config_path)
		
		pass