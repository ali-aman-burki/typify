import subprocess, sys, json

from pathlib import Path
from typing import Union

class SetupUtils:
	@staticmethod
	def extract_runtime_env(python_executable=sys.executable) -> dict[str, Union[str, Path, list[Path]]]:
		script = """
import sys, site, sysconfig, json

info = {
	"sys_path": sys.path,
	"site_packages": site.getsitepackages(),
	"user_site_packages": site.getusersitepackages(),
	"stdlib": sysconfig.get_paths()["stdlib"],
	"builtins": "nonexistent/so/far",
	"executable": sys.executable,
	"version": sys.version,
	"platform": sys.platform,
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

		def to_path_list(value):
			if isinstance(value, list):
				return [Path(p) for p in value]
			return Path(value)

		return {
			"sys_path": to_path_list(raw_info["sys_path"]),
			"site_packages": to_path_list(raw_info["site_packages"]),
			"user_site_packages": Path(raw_info["user_site_packages"]),
			"stdlib": Path(raw_info["stdlib"]),
			"builtins": Path(raw_info["builtins"]),
			"executable": Path(raw_info["executable"]),
			"version": raw_info["version"],
			"platform": raw_info["platform"],
		}