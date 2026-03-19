"""Python tree-sitter parser — extracts functions, classes, imports, tests, and constants."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import structlog
from tree_sitter import Node, Query, QueryCursor
from tree_sitter_language_pack import get_language, get_parser

logger = structlog.get_logger()

# Module-level singletons — created once, reused across files.
_LANGUAGE = get_language("python")
_PARSER = get_parser("python")

# Pre-compiled regex for SCREAMING_SNAKE constant detection.
_SCREAMING_SNAKE_RE = re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$")

# --- Query patterns ---

_FUNC_QUERY = Query(
    _LANGUAGE,
    """
(function_definition
  name: (identifier) @func_name
  parameters: (parameters) @params
  return_type: (_)? @return_type)
""",
)

_CLASS_QUERY = Query(
    _LANGUAGE,
    """
(class_definition
  name: (identifier) @class_name
  superclasses: (argument_list)? @bases)
""",
)

_IMPORT_QUERY = Query(
    _LANGUAGE,
    """
(import_statement
  name: (dotted_name) @module)
""",
)

_IMPORT_FROM_QUERY = Query(
    _LANGUAGE,
    """
(import_from_statement
  module_name: (dotted_name) @source)
""",
)

_TEST_FUNC_QUERY = Query(
    _LANGUAGE,
    """
(function_definition
  name: (identifier) @test_func
  (#match? @test_func "^test_"))
""",
)


@dataclass(frozen=True)
class ParsedFunction:
    """A parsed function definition."""

    name: str
    line_start: int
    line_end: int
    has_return_type: bool
    param_count: int
    annotated_param_count: int
    has_docstring: bool
    decorators: tuple[str, ...]
    is_test: bool


@dataclass(frozen=True)
class ParsedClass:
    """A parsed class definition."""

    name: str
    line_start: int
    line_end: int
    bases: tuple[str, ...]
    has_docstring: bool


@dataclass(frozen=True)
class ParsedImport:
    """A parsed import statement."""

    module: str
    is_relative: bool


@dataclass(frozen=True)
class ParsedPythonFile:
    """Structured result from parsing a Python source file."""

    path: str
    functions: tuple[ParsedFunction, ...]
    classes: tuple[ParsedClass, ...]
    imports: tuple[ParsedImport, ...]
    constants: tuple[str, ...]
    has_errors: bool


def _text(node: Node) -> str:
    """Decode node text from bytes to str."""
    raw = node.text
    if raw is None:
        return ""
    return raw.decode("utf8")


def _has_docstring(body_node: Node | None) -> bool:
    """Check if a function/class body starts with a docstring."""
    if body_node is None:
        return False
    for child in body_node.children:
        # Docstring can appear directly as a string node in the body
        if child.type == "string":
            return True
        # Or wrapped in an expression_statement
        if child.type == "expression_statement":
            return any(grandchild.type == "string" for grandchild in child.children)
        if child.type == "comment":
            continue
        return False
    return False


def _get_body(node: Node) -> Node | None:
    """Get the body (block) child of a function/class definition."""
    return node.child_by_field_name("body")


def _get_decorators(func_node: Node) -> tuple[str, ...]:
    """Extract decorator names from a function definition."""
    decorators: list[str] = []
    # Decorators are siblings before the function_definition in a decorated_definition
    parent = func_node.parent
    if parent is not None and parent.type == "decorated_definition":
        for child in parent.children:
            if child.type == "decorator":
                # The decorator content is everything after @
                dec_text = _text(child).lstrip("@").strip()
                decorators.append(dec_text)
    return tuple(decorators)


def _count_annotated_params(params_node: Node) -> tuple[int, int]:
    """Count total and annotated parameters (excluding self/cls)."""
    total = 0
    annotated = 0
    for child in params_node.children:
        if child.type in (
            "identifier",
            "typed_parameter",
            "default_parameter",
            "typed_default_parameter",
        ):
            name_text = ""
            if child.type == "identifier":
                name_text = _text(child)
            elif child.type in ("typed_parameter", "default_parameter", "typed_default_parameter"):
                name_node = child.child_by_field_name("name")
                if name_node is not None:
                    name_text = _text(name_node)

            if name_text in ("self", "cls"):
                continue
            total += 1
            if child.type in ("typed_parameter", "typed_default_parameter"):
                annotated += 1
    return total, annotated


def _has_tree_errors(root: Node) -> bool:
    """Check if the tree contains ERROR nodes using an iterative approach."""
    stack: list[Node] = [root]
    while stack:
        node = stack.pop()
        if node.type == "ERROR":
            return True
        stack.extend(node.children)
    return False


def _extract_constants(root: Node) -> tuple[str, ...]:
    """Extract module-level constant names (SCREAMING_SNAKE assignments)."""
    constants: list[str] = []
    for child in root.children:
        # Assignments may be direct children or wrapped in expression_statement
        assignment = None
        if child.type == "assignment":
            assignment = child
        elif child.type == "expression_statement":
            first = child.children[0] if child.children else None
            if first is not None and first.type == "assignment":
                assignment = first

        if assignment is not None:
            left = assignment.child_by_field_name("left")
            if left is not None and left.type == "identifier":
                name = _text(left)
                if _SCREAMING_SNAKE_RE.match(name):
                    constants.append(name)
    return tuple(constants)


def parse_python_file(path: Path, source: bytes | None = None) -> ParsedPythonFile:
    """Parse a Python source file and extract structured data.

    If source is not provided, reads from path. Returns a ParsedPythonFile
    even if the file has syntax errors (tree-sitter always produces a tree).
    """
    if source is None:
        try:
            source = path.read_bytes()
        except OSError as exc:
            logger.warning("Failed to read Python file", path=str(path), error=str(exc))
            return ParsedPythonFile(
                path=str(path), functions=(), classes=(), imports=(), constants=(), has_errors=True
            )

    tree = _PARSER.parse(source)
    root = tree.root_node
    has_errors = _has_tree_errors(root)

    if has_errors:
        logger.warning("Python file has parse errors", path=str(path))

    functions = _extract_functions(root)
    classes = _extract_classes(root)
    imports = _extract_imports(root)
    constants = _extract_constants(root)

    return ParsedPythonFile(
        path=str(path),
        functions=functions,
        classes=classes,
        imports=imports,
        constants=constants,
        has_errors=has_errors,
    )


def _extract_functions(root: Node) -> tuple[ParsedFunction, ...]:
    """Extract all function definitions from the tree.

    Uses parent-node lookup (not index correlation) to match captures
    to their owning function_definition, avoiding non-deterministic ordering.
    """
    cursor = QueryCursor(_FUNC_QUERY)
    captures = cursor.captures(root)

    # Collect test function names for is_test detection
    test_cursor = QueryCursor(_TEST_FUNC_QUERY)
    test_captures = test_cursor.captures(root)
    test_names = {_text(n) for n in test_captures.get("test_func", [])}

    func_name_nodes = captures.get("func_name", [])
    params_nodes = captures.get("params", [])
    return_type_nodes = captures.get("return_type", [])

    # Build lookup maps by parent function_definition tree-sitter node.id
    # (not Python id() which differs across wrapper objects for the same node)
    params_by_func: dict[int, Node] = {}
    for p_node in params_nodes:
        if p_node.parent is not None:
            params_by_func[p_node.parent.id] = p_node

    return_type_func_ids: set[int] = set()
    for rt_node in return_type_nodes:
        parent = rt_node.parent
        if parent is not None and parent.type == "function_definition":
            return_type_func_ids.add(parent.id)

    functions: list[ParsedFunction] = []
    for name_node in func_name_nodes:
        name = _text(name_node)
        func_def = name_node.parent
        if func_def is None:
            continue

        line_start = func_def.start_point[0] + 1  # 1-indexed
        line_end = func_def.end_point[0] + 1

        # Look up params by tree-sitter node.id, not by list index
        params_node = params_by_func.get(func_def.id)
        param_count = 0
        annotated_count = 0
        if params_node is not None:
            param_count, annotated_count = _count_annotated_params(params_node)

        has_return_type = func_def.id in return_type_func_ids

        body = _get_body(func_def)
        has_docstring = _has_docstring(body)
        decorators = _get_decorators(func_def)
        is_test = name in test_names

        functions.append(
            ParsedFunction(
                name=name,
                line_start=line_start,
                line_end=line_end,
                has_return_type=has_return_type,
                param_count=param_count,
                annotated_param_count=annotated_count,
                has_docstring=has_docstring,
                decorators=decorators,
                is_test=is_test,
            )
        )

    return tuple(functions)


def _extract_classes(root: Node) -> tuple[ParsedClass, ...]:
    """Extract all class definitions from the tree."""
    cursor = QueryCursor(_CLASS_QUERY)
    captures = cursor.captures(root)

    class_name_nodes = captures.get("class_name", [])
    bases_nodes = captures.get("bases", [])

    # Build bases lookup by parent class_definition tree-sitter node.id
    bases_by_class: dict[int, tuple[str, ...]] = {}
    for bases_node in bases_nodes:
        parent = bases_node.parent
        if parent is not None and parent.type == "class_definition":
            base_names = tuple(
                _text(child) for child in bases_node.children if child.type not in ("(", ")", ",")
            )
            bases_by_class[parent.id] = base_names

    classes: list[ParsedClass] = []
    for name_node in class_name_nodes:
        name = _text(name_node)
        class_def = name_node.parent
        if class_def is None:
            continue

        line_start = class_def.start_point[0] + 1
        line_end = class_def.end_point[0] + 1

        bases = bases_by_class.get(class_def.id, ())

        body = _get_body(class_def)
        has_docstring = _has_docstring(body)

        classes.append(
            ParsedClass(
                name=name,
                line_start=line_start,
                line_end=line_end,
                bases=bases,
                has_docstring=has_docstring,
            )
        )

    return tuple(classes)


def _extract_imports(root: Node) -> tuple[ParsedImport, ...]:
    """Extract all import statements from the tree.

    Handles both absolute imports (import X, from X import Y) and
    relative imports (from . import Y, from ..X import Y) by walking
    the tree for import_from_statement nodes with relative_import children.
    """
    imports: list[ParsedImport] = []

    # Regular imports (import X)
    cursor = QueryCursor(_IMPORT_QUERY)
    captures = cursor.captures(root)
    imports.extend(
        ParsedImport(module=_text(node), is_relative=False) for node in captures.get("module", [])
    )

    # From imports with dotted_name (from X import Y — absolute)
    cursor2 = QueryCursor(_IMPORT_FROM_QUERY)
    captures2 = cursor2.captures(root)
    imports.extend(
        ParsedImport(module=_text(node), is_relative=False) for node in captures2.get("source", [])
    )

    # Walk tree for relative imports (from . import Y, from ..X import Y)
    # These have relative_import as module_name, not dotted_name, so the
    # query above won't match them.
    _collect_relative_imports(root, imports)

    return tuple(imports)


def _collect_relative_imports(node: Node, imports: list[ParsedImport]) -> None:
    """Walk the tree to find import_from_statement nodes with relative imports."""
    if node.type == "import_from_statement":
        module_name = node.child_by_field_name("module_name")
        if module_name is not None and module_name.type == "relative_import":
            # Extract the dotted_name inside the relative_import, if any
            for child in module_name.children:
                if child.type == "dotted_name":
                    imports.append(ParsedImport(module=_text(child), is_relative=True))
                    return
            # Bare relative import (from . import X) — no dotted_name
            imports.append(ParsedImport(module=".", is_relative=True))
            return
    for child in node.children:
        _collect_relative_imports(child, imports)
