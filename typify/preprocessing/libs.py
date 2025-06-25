from typify.preprocessing.library_meta import LibraryMeta

class RequiredLibs:
    preloaded: dict[str, LibraryMeta] = None
    ondemand: dict[str, LibraryMeta] = None