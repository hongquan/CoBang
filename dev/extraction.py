"""Extract custom GObject-based class composition hierarchy from src/."""

from __future__ import annotations

import ast
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

import click


# Known GObject namespaces likely to appear as base classes in src/.
KNOWN_GOBJECT_NS = frozenset({
    'GObject', 'Gtk', 'Gdk', 'Adw', 'Gio', 'GLib', 'Gst', 'NM', 'Xdp',
    'Pango', 'Graphene', 'GdkPixbuf', 'Soup', 'WebKit',
})


def display_width(s: str) -> int:
    """Return the display width of a string, accounting for double-width chars."""
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)


class ClassInfo(NamedTuple):
    name: str
    file: str       # relative to project root
    line: int


def qualname(node: ast.expr) -> str | None:
    """Return a dotted qualname for an AST expression, e.g. 'Adw.Bin'."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = qualname(node.value)
        return f'{base}.{node.attr}' if base else None
    return None


def is_gobject_base(dotted: str) -> bool:
    """Check if a dotted name refers to a known GObject base."""
    return dotted.split('.')[0] in KNOWN_GOBJECT_NS


def collect_classes(project_root: Path) -> dict[str, ClassInfo]:
    """Walk src/ and collect all custom GObject-based class definitions."""
    raw: dict[str, ClassInfo] = {}
    src_dir = project_root / 'src'

    for py_file in sorted(src_dir.rglob('*.py')):
        rel = str(py_file.relative_to(project_root))
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                qn = qualname(base)
                if qn and is_gobject_base(qn):
                    raw[node.name] = ClassInfo(
                        name=node.name,
                        file=rel,
                        line=node.lineno,
                    )
                    break

    # Filter out data classes (GObject.GObject direct subclass without .blp template)
    data_classes = {
        name for name, info in raw.items()
        if is_data_class(name, raw, project_root)
    }
    return {
        name: info
        for name, info in raw.items()
        if name not in data_classes
    }


def has_template_file(class_name: str, project_root: Path) -> bool:
    """Check if a .blp template file exists for this class."""
    src_ui = project_root / 'src' / 'ui'
    if not src_ui.is_dir():
        return False
    for blp_file in src_ui.rglob('*.blp'):
        content = blp_file.read_text()
        if f'$ {class_name}' in content or f'template ${class_name}' in content:
            return True
    return False


def is_data_class(name: str, classes: dict[str, ClassInfo], project_root: Path) -> bool:
    """Heuristic: a class is a data object if it inherits directly from GObject.GObject
    and has no .blp template file."""
    cls_info = classes.get(name)
    if not cls_info:
        return False
    py_file = project_root / cls_info.file
    try:
        tree = ast.parse(py_file.read_text())
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != name:
            continue
        for base in node.bases:
            qn = qualname(base)
            if qn == 'GObject.GObject' and not has_template_file(name, project_root):
                return True
    return False


def collect_template_child_parents(tree: ast.Module) -> list[tuple[str, str]]:
    """Find Template.Child() declarations and their enclosing class.

    Returns list of (parent_class, child_type_name).
    """
    results: list[tuple[str, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if (isinstance(item, ast.AnnAssign)
                    and isinstance(item.value, ast.Call)
                    and isinstance(item.value.func, ast.Attribute)
                    and item.value.func.attr == 'Child'):
                # Extract type name from annotation
                if isinstance(item.annotation, ast.Name):
                    results.append((node.name, item.annotation.id))
                elif isinstance(item.annotation, ast.Subscript):
                    # e.g. Optional[SomeType]
                    if isinstance(item.annotation.value, ast.Name):
                        results.append((node.name, item.annotation.value.id))

    return results


def collect_direct_instantiations(tree: ast.Module, known_names: set[str]) -> list[tuple[str, str]]:
    """Find ClassName(...) calls inside methods, enclosed by a class.

    Returns list of (parent_class, instantiated_name).
    Only captures calls inside method bodies (not class-level statements).
    """
    results: list[tuple[str, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for call_node in ast.walk(item):
                    if (isinstance(call_node, ast.Call)
                            and isinstance(call_node.func, ast.Name)
                            and call_node.func.id in known_names):
                        results.append((node.name, call_node.func.id))

    return results


def build_edges(classes: dict[str, ClassInfo], project_root: Path) -> list[tuple[str, str]]:
    """Build parent→child edges from Template.Child and direct instantiations."""
    known_names = set(classes.keys())
    edges: list[tuple[str, str]] = []

    src_dir = project_root / 'src'
    for py_file in sorted(src_dir.rglob('*.py')):
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue

        # Template.Child declarations
        for parent, child in collect_template_child_parents(tree):
            if parent in known_names and child in known_names:
                edges.append((parent, child))

        # Direct instantiations in methods
        for parent, child in collect_direct_instantiations(tree, known_names):
            if parent in known_names and child in known_names:
                edges.append((parent, child))

    # Filter out data-class children
    data_classes = {
        name for name in classes
        if is_data_class(name, classes, project_root)
    }
    return [(p, c) for p, c in edges if c not in data_classes]


def find_app_entry_points(classes: dict[str, ClassInfo]) -> set[str]:
    """Find Application-level classes (entry points into the widget tree)."""
    entry_points: set[str] = set()
    dev_dir = Path(__file__).resolve().parent
    for name, info in classes.items():
        try:
            tree = ast.parse((dev_dir.parent / info.file).read_text())
        except (SyntaxError, FileNotFoundError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name != name:
                continue
            for base in node.bases:
                qn = qualname(base)
                if qn and qn.startswith(('Gtk.Application', 'Adw.Application')):
                    entry_points.add(name)
                    break
    return entry_points


def build_tree(
    classes: dict[str, ClassInfo],
    edges: list[tuple[str, str]],
) -> tuple[dict[str, list[str]], set[str]]:
    """Build adjacency list: parent → [children].

    Only keeps classes reachable from Application entry points.
    Returns (children_map, kept_classes).
    """
    children_map: dict[str, list[str]] = defaultdict(list)

    for parent, child in edges:
        if child not in children_map[parent]:
            children_map[parent].append(child)

    # Sort children for deterministic output
    for k in children_map:
        children_map[k].sort()

    # Find entry points (Application subclasses)
    entry_points = find_app_entry_points(classes)

    # BFS from entry points to find all reachable classes
    reachable: set[str] = set()
    queue = list(entry_points)
    while queue:
        current = queue.pop(0)
        if current in reachable:
            continue
        reachable.add(current)
        for child in children_map.get(current, []):
            if child not in reachable:
                queue.append(child)

    # Prune unreachable nodes
    for name in list(children_map):
        if name not in reachable:
            del children_map[name]
    for kids in children_map.values():
        kids[:] = [c for c in kids if c in reachable]

    return dict(children_map), reachable


def render_tree(
    classes: dict[str, ClassInfo],
    children_map: dict[str, list[str]],
    kept_classes: set[str] | None = None,
) -> str:
    """Render the composition hierarchy as an ASCII tree."""
    if kept_classes is None:
        kept_classes = set(classes.keys())

    # Find roots: classes that are never a child AND are kept
    all_children: set[str] = set()
    for kids in children_map.values():
        all_children.update(kids)

    roots = [name for name in kept_classes if name not in all_children]
    roots.sort(key=lambda n: classes[n].file)

    # Connectors and extensions
    conn_last = '└─ '
    conn_mid = '├─ '
    ext_last = '    '   # 4 spaces
    ext_mid = '│   '    # │ + 3 spaces

    # First pass: compute max display width of (prefix + connector + name)
    def max_width(name: str, prefix: str, is_root: bool) -> int:
        connector = '' if is_root else conn_mid
        cw = display_width(prefix) + display_width(connector) + display_width(name)
        kids = children_map.get(name, [])
        for idx, child in enumerate(kids):
            child_is_last = (idx == len(kids) - 1)
            if is_root:
                ext = ' '
            else:
                ext = ext_last if child_is_last else ext_mid
            cw = max(cw, max_width(child, prefix + ext, False))
        return cw

    max_total = 0
    for root in roots:
        max_total = max(max_total, max_width(root, '', True))

    lines: list[str] = []

    def _render(name: str, prefix: str, is_last: bool, is_root: bool) -> None:
        cls = classes[name]
        if is_root:
            connector = ''
        else:
            connector = conn_last if is_last else conn_mid
        node_width = display_width(prefix) + display_width(connector) + display_width(name)
        padding = ' ' * (max_total - node_width + 3)
        lines.append(f'{prefix}{connector}{name}{padding}({cls.file}:{cls.line})')
        kids = children_map.get(name, [])
        for idx, child in enumerate(kids):
            child_is_last = (idx == len(kids) - 1)
            extension = ' ' if is_root else (ext_last if is_last else ext_mid)
            _render(child, prefix + extension, child_is_last, False)

    for idx, root in enumerate(roots):
        _render(root, '', idx == len(roots) - 1, True)

    return '\n'.join(lines)


@click.command(
    'extract-widget-hierarchy',
    help='Extract custom widget composition hierarchy from src/.',
)
def extract_widget_hierarchy() -> None:
    project_root = Path(__file__).resolve().parent.parent
    classes = collect_classes(project_root)
    edges = build_edges(classes, project_root)
    children_map, kept_classes = build_tree(classes, edges)
    output = render_tree(classes, children_map, kept_classes)
    click.echo(output)
