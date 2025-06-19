import subprocess, sys, json, re

from pathlib import Path
from typing import Union

class SetupUtils:

	@staticmethod
	def extract_runtime_env(python_executable=sys.executable) -> dict[str, Union[str, Path, list[Path]]]:
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
	def get_paths(config_path: Path):
		defaults = SetupUtils.extract_runtime_env()

		with open(config_path, "r") as f:
			config: dict[str, str | dict[str, str]] = json.load(f)

		man_libs = config["man_libs"]
		for key in man_libs:
			config["paths"] = config["paths"].replace("{" + key + "}", man_libs[key])

		if config["paths"] == "{auto}":
			return (
				[Path(config["project_dir"]),
				Path(man_libs["builtinlib"]),
				Path(man_libs["stdlib"]),
				Path(defaults["user_site_lib"])] +
				[Path(p) for p in defaults["site_libs"]]
			)
		else:
			raw_paths = [Path(p) for p in re.split(r"\s*,\s*", config["paths"])]
			project_dir = Path(config["project_dir"])
			builtinlib = Path(man_libs["builtinlib"])

			raw_paths = [p for p in raw_paths if p != project_dir and p != builtinlib]
			final_paths = [project_dir, builtinlib] + raw_paths
			return final_paths

	@staticmethod
	def preprocess_libs(config_path: Path): 
		paths = SetupUtils.get_paths(config_path)
		
		pass