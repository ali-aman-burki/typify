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
            "builtin_lib": "{auto}",
            "pystd_lib": "{auto}",
        },
        "paths": "{auto}"
    }
    result1 = SetupUtils.get_paths(write_config(config1))
    print_result(1, result1)

    # Test 2: Custom paths using templates (but builtin_lib should move to index 1)
    config2 = {
        "project_dir": str(project_dir),
        "output_dir": "/some/ignored",
        "man_libs": {
            "builtin_lib": "{auto}",
            "pystd_lib": "{auto}",
			"other_lib": "/other/lib"
        },
        "paths": "{builtin_lib}, /extra, {pystd_lib}, {other_lib}"
    }
    result2 = SetupUtils.get_paths(write_config(config2))
    print_result(2, result2)

    # Test 3: Manual override of builtin_lib
    custom_builtin = Path("/my/custom/builtin")
    config3 = {
        "project_dir": str(project_dir),
        "output_dir": "/some/ignored",
        "man_libs": {
            "builtin_lib": str(custom_builtin),
            "pystd_lib": "{auto}"
        },
        "paths": "{builtin_lib}, {pystd_lib}"
    }
    result3 = SetupUtils.get_paths(write_config(config3))
    print_result(3, result3)

    config4 = {
        "project_dir": str(project_dir),
        "output_dir": "/some/ignored",
        "man_libs": {
            "builtin_lib": "{auto}",
            "pystd_lib": "{auto}"
        },
        "paths": "/a, /b, /c"
    }
    result4 = SetupUtils.get_paths(write_config(config4))
    print_result(4, result4)

    print("\n✅ no errors.")

if __name__ == "__main__":
    run_tests()
