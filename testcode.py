import tempfile
import json
from pathlib import Path
from src.preloading.setup_utils import SetupUtils

def run_tests():
    defaults = SetupUtils.extract_runtime_env()

    def write_config(data: dict) -> Path:
        f = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json")
        json.dump(data, f)
        f.close()
        return Path(f.name)

    def print_result(n: int, result: list[Path]):
        print(f"\n--- Test {n} Resolved Paths ---")
        for p in result:
            print(p)

    project_dir = Path("/some/proj")

    # Test 1: All auto
    config1 = {
        "project_dir": str(project_dir),
        "output_dir": "/some/ignored",
        "man_libs": {
            "builtinlib": "some_path",
            "stdlib": "stdlib/path",
        },
        "paths": "/aanother_path, {stdlib}"
    }
    result1 = SetupUtils.get_paths(write_config(config1))
    print_result(1, result1)

    # Test 2: Custom paths using templates (but builtinlib should move to index 1)
    config2 = {
        "project_dir": str(project_dir),
        "output_dir": "/some/ignored",
        "man_libs": {
            "builtinlib": "{auto}",
            "stdlib": "{auto}",
			"other_lib": "/other/lib"
        },
        "paths": "{builtinlib}, /extra, {stdlib}, {other_lib}"
    }
    result2 = SetupUtils.get_paths(write_config(config2))
    print_result(2, result2)

    # Test 3: Manual override of builtinlib
    custom_builtin = Path("/my/custom/builtin")
    config3 = {
        "project_dir": str(project_dir),
        "output_dir": "/some/ignored",
        "man_libs": {
            "builtinlib": str(custom_builtin),
            "stdlib": "{auto}"
        },
        "paths": "{builtinlib}, {stdlib}"
    }
    result3 = SetupUtils.get_paths(write_config(config3))
    print_result(3, result3)

    config4 = {
        "project_dir": str(project_dir),
        "output_dir": "/some/ignored",
        "man_libs": {
            "builtinlib": "{auto}",
            "stdlib": "{auto}"
        },
        "paths": "/a, /b, /c"
    }
    result4 = SetupUtils.get_paths(write_config(config4))
    print_result(4, result4)

    print("\n✅ no errors.")

if __name__ == "__main__":
    run_tests()
