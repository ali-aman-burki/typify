import subprocess, sys, json, re

from pathlib import Path
from typing import Union

class SetupUtils:

	@staticmethod
	def extract_runtime_env(python_executable=sys.executable) -> dict[str, Union[str, Path, list[Path]]]:
		script = """
import sys, site, sysconfig, json

info = {
	"builtin_lib": "/path/to/builtins_stubs",
	"pystd_lib": sysconfig.get_paths()["stdlib"],
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
			"builtin_lib": raw_info["builtin_lib"],
			"pystd_lib": raw_info["pystd_lib"],
			"user_site_lib": raw_info["user_site_lib"],
			"site_libs": raw_info["site_libs"],
		}
	
	@staticmethod
	def get_paths(config_path: Path):
		defaults = SetupUtils.extract_runtime_env()

		with open(config_path, "r") as f:
			config: dict[str, str | dict[str, str]] = json.load(f)

		man_libs = config["man_libs"]
		for key, val in man_libs.items():
			if val == "{auto}":
				if key not in defaults:
					raise SystemExit(
						f"'{key}' not found in the current Typify Configuration Environment. "
						f"Please check the config file at {config_path}"
					)
				resolved = defaults[key]
			else:
				resolved = val
			man_libs[key] = resolved
			if isinstance(config["paths"], str):
				config["paths"] = config["paths"].replace("{" + key + "}", resolved)

		if config["paths"] == "{auto}":
			return (
				[Path(config["project_dir"]),
				Path(man_libs["builtin_lib"]),
				Path(man_libs["pystd_lib"]),
				Path(defaults["user_site_lib"])] +
				[Path(p) for p in defaults["site_libs"]]
			)
		else:
			raw_paths = [Path(p) for p in re.split(r"\s*,\s*", config["paths"])]
			project_dir = Path(config["project_dir"])
			builtin_lib = Path(man_libs["builtin_lib"])

			raw_paths = [p for p in raw_paths if p != project_dir and p != builtin_lib]
			final_paths = [project_dir, builtin_lib] + raw_paths
			return final_paths

	@staticmethod
	def build_libraries(): pass