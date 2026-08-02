"""Class-hierarchy introspection for the map editor: resolving forward-ref
type hints, walking src/ to find subclasses of a base class (including
transitive descendants reached through an intermediate class), and caching
that expensive AST-parse walk.
"""
import ast
import importlib
import inspect
import os
from tkinter import messagebox
from typing import Dict, List, Optional, Set, Tuple, Union, get_args, get_origin

from utils.mapgen.constants import project_root


def parse_type_hint(annotation):
    """
    Parse a type annotation to determine if it's a class type or list of class types.
    Returns tuple: (base_class, is_list, is_optional)
    """
    if annotation is None or annotation is inspect._empty:
        return None, False, False

    # Handle string annotations (forward references)
    if isinstance(annotation, str):
        # Handle list[...] forward reference in string annotations
        stripped = annotation.strip()
        if (
            stripped.startswith("list[") or stripped.startswith("List[")
        ) and stripped.endswith("]"):
            # extract inner type
            inner = stripped[stripped.index("[") + 1 : -1].strip("'\"")
            base_cls, _, is_opt = parse_type_hint(inner)
            return base_cls, True, is_opt
        try:
            # Try to resolve the string annotation
            # For forward references like 'Item', we need to look up in the appropriate module
            if annotation.startswith("'") and annotation.endswith("'"):
                annotation = annotation[1:-1]

            # Try to import from src modules
            for module_name in ["items", "objects", "npc", "events"]:
                try:
                    module = importlib.import_module(module_name)
                    if hasattr(module, annotation):
                        return getattr(module, annotation), False, False
                except ImportError:
                    continue
        except Exception:
            pass
        return None, False, False

    # Handle typing constructs
    origin = get_origin(annotation)
    args = get_args(annotation)

    # Handle Optional[T] or Union[T, None]
    if origin is Union:
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1:
            # This is Optional[T]
            base_class, is_list, _ = parse_type_hint(non_none_args[0])
            return base_class, is_list, True

    # Handle List[T]
    elif origin is list or origin is List:
        if args:
            base_class, _, is_optional = parse_type_hint(args[0])
            return base_class, True, is_optional

    # Handle direct class references
    elif inspect.isclass(annotation):
        return annotation, False, False

    return None, False, False


def get_class_hierarchy(base_class, module_names=None):
    """
    Get all subclasses of a given base class from specified modules.
    Returns a dictionary mapping class names to class objects.
    """
    if not base_class:
        return {}

    if module_names is None:
        module_names = ["items", "objects", "npc", "events"]

    hierarchy = {base_class.__name__: base_class}

    # Add the base class itself

    # Search through specified modules
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, base_class)
                    and attr is not base_class
                ):
                    hierarchy[attr.__name__] = attr
        except ImportError:
            continue

    return hierarchy


# Cache for _scan_class_hierarchy: (src_dir, src_dir_signature, class_bases,
# class_files). Populated lazily on first call; invalidated whenever src_dir
# changes or its newest mtime changes. Keying on src_dir too (not just the
# mtime signature) matters because this cache now outlives a single test's
# module (re)import -- utils.mapgen.class_discovery isn't among the modules
# test fixtures pop from sys.modules between tests, unlike the old single-file
# utils/map_generator.py, where re-importing the whole module reset this
# cache for free. Without the src_dir in the key, two different directories
# whose newest-mtime happens to match to the second (e.g. two tests using
# separate tmp_path fixtures created in the same wall-clock second) could
# silently return each other's cached results.
_CLASS_HIERARCHY_SCAN_CACHE: Optional[
    Tuple[str, float, Dict[str, Set[str]], Dict[str, Set[str]]]
] = None


def _src_tree_signature(src_dir: str) -> float:
    """Cheap staleness signature for the src/ tree: the newest mtime among all
    .py files under it. A directory walk that only stats each file is far
    cheaper than reading and AST-parsing every file's contents, so this is
    used to gate _scan_class_hierarchy's cache without needing to re-run the
    expensive scan on every call to check whether anything changed.
    """
    newest = 0.0
    for dirpath, _dirnames, filenames in os.walk(src_dir):
        for filename in filenames:
            if not (filename.endswith(".py") and not filename.startswith("__")):
                continue
            try:
                mtime = os.path.getmtime(os.path.join(dirpath, filename))
            except OSError:
                continue
            if mtime > newest:
                newest = mtime
    return newest


def _scan_class_hierarchy(
    src_dir: str,
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Walks src/ once, AST-parsing every module to build a class-name ->
    immediate-base-names map and a class-name -> defining-file-paths map
    (with aliased-import bases resolved to their original name).

    This is the expensive part of _get_module_paths_for_class and is
    independent of which class is being queried, so it's cached process-wide
    and shared across every "Choose" dialog opened in an editing session --
    previously the full tree was re-walked and re-parsed on every single
    button click, regardless of which class_name was requested.
    """
    global _CLASS_HIERARCHY_SCAN_CACHE
    signature = _src_tree_signature(src_dir)
    if (
        _CLASS_HIERARCHY_SCAN_CACHE is not None
        and _CLASS_HIERARCHY_SCAN_CACHE[0] == src_dir
        and _CLASS_HIERARCHY_SCAN_CACHE[1] == signature
    ):
        return _CLASS_HIERARCHY_SCAN_CACHE[2], _CLASS_HIERARCHY_SCAN_CACHE[3]

    # name -> set of immediate base names (by their local, possibly-aliased
    # spelling in that file)
    class_bases: Dict[str, Set[str]] = {}
    # name -> set of absolute file paths where a class of that name is defined
    class_files: Dict[str, Set[str]] = {}
    # local alias name -> original imported name (e.g. "FriendBase" -> "Friend")
    alias_to_real: Dict[str, str] = {}

    for dirpath, dirnames, filenames in os.walk(src_dir):
        for filename in filenames:
            if not (filename.endswith(".py") and not filename.startswith("__")):
                continue
            file_path = os.path.join(dirpath, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    src = f.read()
                tree = ast.parse(src)
            except Exception:
                continue  # Ignore parse errors

            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        if alias.asname:
                            alias_to_real[alias.asname] = alias.name
                elif isinstance(node, ast.ClassDef):
                    bases: Set[str] = set()
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            bases.add(base.id)
                        elif isinstance(base, ast.Attribute):
                            bases.add(base.attr)
                    class_bases.setdefault(node.name, set()).update(bases)
                    class_files.setdefault(node.name, set()).add(file_path)

    # Resolve aliased bases to their original name so the fixpoint in
    # _get_module_paths_for_class can match through an alias (e.g.
    # `class Foo(FriendBase)` where `FriendBase` is `Friend` imported under
    # an alias).
    for name, bases in class_bases.items():
        aliased = {alias_to_real[b] for b in bases if b in alias_to_real}
        if aliased:
            class_bases[name] = bases | aliased

    _CLASS_HIERARCHY_SCAN_CACHE = (src_dir, signature, class_bases, class_files)
    return class_bases, class_files


def _get_module_paths_for_class(class_name: str) -> List[str]:
    """
    Returns a list of absolute file paths for all modules in src/ that define
    the given class or any *transitive* descendant of it (not just direct
    subclasses).

    A naive single-pass AST scan only catches classes whose bases literally
    name `class_name` (e.g. `Merchant(NPC, ...)`). That misses descendants
    reached through an intermediate class -- e.g. concrete Friend NPCs in
    `src/npc/_friends.py` inherit from `Friend` (defined in
    `src/npc/_base.py`), not from `NPC` directly, so a direct-base-only scan
    silently omits `_friends.py` for an `NPC` query (issue #462).

    To fix this we first build a whole-tree map of every class name to its
    immediate base names and defining file(s) (see _scan_class_hierarchy),
    then run a fixpoint over that graph: start with `{class_name}` and
    repeatedly add any class whose base set intersects the current matched
    set, until a pass adds nothing new. Because `matched` only ever grows and
    the class universe is finite, this always terminates -- including in the
    presence of inheritance cycles (which shouldn't exist in valid Python but
    a bug/typo elsewhere shouldn't turn into an infinite loop here).
    """
    src_dir = os.path.join(project_root, "src")

    class_bases, class_files = _scan_class_hierarchy(src_dir)

    # Fixpoint: grow the matched set until a full pass adds nothing new.
    matched: Set[str] = {class_name}
    changed = True
    while changed:
        changed = False
        for name, bases in class_bases.items():
            if name in matched:
                continue
            if bases & matched:
                matched.add(name)
                changed = True

    result_paths: Set[str] = set()
    for name in matched:
        result_paths.update(class_files.get(name, ()))
    return list(result_paths)


def get_import_path(module_path, this_project_root):
    rel = os.path.relpath(module_path, this_project_root)
    import_mod = rel.replace(os.sep, ".")
    if import_mod.lower().endswith(".py"):
        import_mod = import_mod[:-3]
    if import_mod.startswith("src."):
        import_mod = import_mod[4:]
    return import_mod


def parse_module_classes(module_path, this_project_root):
    class_info = {}
    if not os.path.isfile(module_path):
        return class_info
    try:
        with open(module_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except Exception as e:
        messagebox.showerror("Error", f"Could not load module {module_path}:\n{e}")
        return None
    import_mod = get_import_path(module_path, this_project_root)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
                elif isinstance(b, ast.Attribute):
                    bases.append(b.attr)
            info = class_info.setdefault(
                node.name, {"bases": [], "children": set(), "module": import_mod}
            )
            info["bases"] = bases
    return class_info


def build_class_hierarchy(class_info):
    for name, info in class_info.items():
        for base in info["bases"]:
            if base in info["children"]:
                info["children"].remove(base)
            if base in class_info:
                class_info[base]["children"].add(name)
    return class_info


# Issue #463: arena/debug-only NPC classes, excluded from the "Add NPC"
# chooser -- per their own docstrings and the existing
# ADD_COMBATANT_ALLOWED_CLASSES allow-list in npc/_adjutant.py, none of
# these are meant to be placed on a real map. The authored-placeholder
# format still works for them (combat-testing-arena.json keeps loading),
# this only hides them from the palette.
_DEBUG_ONLY_NPC_CLASSES = frozenset({"TheAdjutant", "StatusDummy", "Testexp"})


def filter_classes(class_info, filter_by_class):
    # Filter classes to include the target class and all its subclasses
    allowed_classes = set(class_info.keys())
    if filter_by_class:

        def is_subclass_or_same(cname):
            if cname == filter_by_class:
                return True
            visited = set()

            def check_sub(c):
                if c in visited:
                    return False
                visited.add(c)
                bases = class_info.get(c, {}).get("bases", [])
                for b in bases:
                    if b == filter_by_class:
                        return True
                    if b in class_info and check_sub(b):
                        return True
                return False

            return check_sub(cname)

        allowed_classes = {c for c in class_info if is_subclass_or_same(c)}
    if filter_by_class == "NPC":
        allowed_classes -= _DEBUG_ONLY_NPC_CLASSES
    return allowed_classes

