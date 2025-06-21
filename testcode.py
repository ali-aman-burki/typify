import tempfile
from pathlib import Path
from typify.preprocessing.library_meta import LibraryMeta

def write(p: Path, content=""):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)

with tempfile.TemporaryDirectory() as tempdir:
    temp = Path(tempdir)

    # Test structure
    # /lib/
    # ├── __init__.py
    # ├── py.typed
    # ├── foo.py
    # ├── bar.pyi
    # └── sub/
    #     ├── __init__.py
    #     ├── sub1.py
    #     └── sub2.pyi
    lib_dir = temp / "lib"
    write(lib_dir / "__init__.py")
    write(lib_dir / "py.typed")
    write(lib_dir / "foo.py")
    write(lib_dir / "bar.pyi")

    sub = lib_dir / "sub"
    write(sub / "__init__.py")
    write(sub / "sub1.py")
    write(sub / "sub2.pyi")

    lib = LibraryMeta(lib_dir)

    print("\n[MODULE META FLAGS]")
    for meta in lib.meta_map.values():
        print(f"{meta.src_path.relative_to(temp)} | is_stub: {meta.is_stub:<5} | trust_annotations: {meta.trust_annotations}")
