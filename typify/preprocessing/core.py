from typify.preprocessing.library_meta import LibraryMeta
from typify.preprocessing.module_meta import ModuleMeta

class Global:
    libs: list[LibraryMeta] = []
    inference: dict[str, ModuleMeta] = {}