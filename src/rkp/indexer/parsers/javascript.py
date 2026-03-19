"""JavaScript/TypeScript tree-sitter parser — extracts functions, classes, imports, exports, tests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import structlog
from tree_sitter import Node, Query, QueryCursor
from tree_sitter_language_pack import get_language, get_parser

logger = structlog.get_logger()

# Module-level singletons per grammar — created once, reused across files.
_JS_LANGUAGE = get_language("javascript")
_JS_PARSER = get_parser("javascript")
_TS_LANGUAGE = get_language("typescript")
_TS_PARSER = get_parser("typescript")

# File extension → grammar mapping.
_EXTENSION_GRAMMAR: dict[str, str] = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

# --- Query patterns (JavaScript) ---

_JS_FUNC_QUERY = Query(
    _JS_LANGUAGE,
    """
(function_declaration
  name: (identifier) @func_name)
""",
)

_JS_ARROW_QUERY = Query(
    _JS_LANGUAGE,
    """
(lexical_declaration
  (variable_declarator
    name: (identifier) @func_name
    value: (arrow_function)))
""",
)

_JS_FUNC_EXPR_QUERY = Query(
    _JS_LANGUAGE,
    """
(lexical_declaration
  (variable_declarator
    name: (identifier) @func_name
    value: (function_expression)))
""",
)

_JS_CLASS_QUERY = Query(
    _JS_LANGUAGE,
    """
(class_declaration
  name: (identifier) @class_name)
""",
)

_JS_IMPORT_QUERY = Query(
    _JS_LANGUAGE,
    """
(import_statement
  source: (string) @import_source)
""",
)

_JS_EXPORT_FUNC_QUERY = Query(
    _JS_LANGUAGE,
    """
(export_statement
  declaration: (function_declaration
    name: (identifier) @export_func))
""",
)

_JS_EXPORT_DEFAULT_QUERY = Query(
    _JS_LANGUAGE,
    """
(export_statement
  "default" @default_kw)
""",
)

# --- Query patterns (TypeScript) ---

_TS_FUNC_QUERY = Query(
    _TS_LANGUAGE,
    """
(function_declaration
  name: (identifier) @func_name)
""",
)

_TS_ARROW_QUERY = Query(
    _TS_LANGUAGE,
    """
(lexical_declaration
  (variable_declarator
    name: (identifier) @func_name
    value: (arrow_function)))
""",
)

_TS_FUNC_EXPR_QUERY = Query(
    _TS_LANGUAGE,
    """
(lexical_declaration
  (variable_declarator
    name: (identifier) @func_name
    value: (function_expression)))
""",
)

_TS_CLASS_QUERY = Query(
    _TS_LANGUAGE,
    """
(class_declaration
  name: (type_identifier) @class_name)
""",
)

_TS_IMPORT_QUERY = Query(
    _TS_LANGUAGE,
    """
(import_statement
  source: (string) @import_source)
""",
)

_TS_EXPORT_FUNC_QUERY = Query(
    _TS_LANGUAGE,
    """
(export_statement
  declaration: (function_declaration
    name: (identifier) @export_func))
""",
)

_TS_EXPORT_DEFAULT_QUERY = Query(
    _TS_LANGUAGE,
    """
(export_statement
  "default" @default_kw)
""",
)

# Test function patterns (describe, it, test, expect).
_TEST_CALL_RE = re.compile(r"\b(describe|it|test|expect)\s*\(")


@dataclass(frozen=True)
class ParsedJSFunction:
    """A parsed function/arrow function."""

    name: str
    line_start: int
    line_end: int
    is_arrow: bool
    is_exported: bool


@dataclass(frozen=True)
class ParsedJSClass:
    """A parsed class declaration."""

    name: str
    line_start: int
    line_end: int
    extends: str | None


@dataclass(frozen=True)
class ParsedJSImport:
    """A parsed import statement."""

    source: str
    is_require: bool


@dataclass(frozen=True)
class ParsedJavaScriptFile:
    """Structured result from parsing a JS/TS source file."""

    path: str
    language: str  # "javascript" or "typescript"
    functions: tuple[ParsedJSFunction, ...]
    classes: tuple[ParsedJSClass, ...]
    imports: tuple[ParsedJSImport, ...]
    export_names: tuple[str, ...]
    has_default_export: bool
    has_test_patterns: bool
    has_errors: bool


def _text(node: Node) -> str:
    """Decode node text from bytes to str."""
    raw = node.text
    if raw is None:
        return ""
    return raw.decode("utf8")


def _has_tree_errors(root: Node) -> bool:
    """Check if the tree contains ERROR nodes."""
    stack: list[Node] = [root]
    while stack:
        node = stack.pop()
        if node.type == "ERROR":
            return True
        stack.extend(node.children)
    return False


def _strip_quotes(s: str) -> str:
    """Strip surrounding quotes from a string literal."""
    if len(s) >= 2 and s[0] in ('"', "'", "`") and s[-1] == s[0]:
        return s[1:-1]
    return s


def _get_extends_clause(class_node: Node) -> str | None:
    """Extract the extends clause from a class declaration."""
    for child in class_node.children:
        if child.type == "class_heritage":
            for heritage_child in child.children:
                if heritage_child.type == "extends_clause":
                    for ext_child in heritage_child.children:
                        if ext_child.type in (
                            "identifier",
                            "type_identifier",
                            "member_expression",
                        ):
                            return _text(ext_child)
    return None


def _detect_test_patterns(source: bytes) -> bool:
    """Detect test framework patterns (describe/it/test/expect) in source."""
    try:
        text = source.decode("utf8", errors="replace")
    except Exception:
        return False
    return bool(_TEST_CALL_RE.search(text))


def _collect_require_imports(root: Node) -> list[ParsedJSImport]:
    """Walk tree for CommonJS require() calls."""
    imports: list[ParsedJSImport] = []
    stack: list[Node] = [root]
    while stack:
        node = stack.pop()
        if node.type == "call_expression" and node.child_by_field_name("function") is not None:
            func_node = node.child_by_field_name("function")
            if (
                func_node is not None
                and func_node.type == "identifier"
                and _text(func_node) == "require"
            ):
                args = node.child_by_field_name("arguments")
                if args is not None:
                    for arg in args.children:
                        if arg.type == "string":
                            imports.append(
                                ParsedJSImport(
                                    source=_strip_quotes(_text(arg)),
                                    is_require=True,
                                )
                            )
                            break
        stack.extend(node.children)
    return imports


def parse_javascript_file(path: Path, source: bytes | None = None) -> ParsedJavaScriptFile:
    """Parse a JS/TS source file and extract structured data.

    If source is not provided, reads from path. Returns a ParsedJavaScriptFile
    even if the file has syntax errors (tree-sitter always produces a tree).
    """
    suffix = path.suffix.lower()
    grammar = _EXTENSION_GRAMMAR.get(suffix, "javascript")

    if source is None:
        try:
            source = path.read_bytes()
        except OSError as exc:
            logger.warning("Failed to read JS/TS file", path=str(path), error=str(exc))
            return ParsedJavaScriptFile(
                path=str(path),
                language=grammar,
                functions=(),
                classes=(),
                imports=(),
                export_names=(),
                has_default_export=False,
                has_test_patterns=False,
                has_errors=True,
            )

    if grammar == "typescript":
        parser = _TS_PARSER
        lang = _TS_LANGUAGE
        func_q, arrow_q, func_expr_q = _TS_FUNC_QUERY, _TS_ARROW_QUERY, _TS_FUNC_EXPR_QUERY
        class_q = _TS_CLASS_QUERY
        import_q = _TS_IMPORT_QUERY
        export_func_q = _TS_EXPORT_FUNC_QUERY
        export_default_q = _TS_EXPORT_DEFAULT_QUERY
    else:
        parser = _JS_PARSER
        lang = _JS_LANGUAGE
        func_q, arrow_q, func_expr_q = _JS_FUNC_QUERY, _JS_ARROW_QUERY, _JS_FUNC_EXPR_QUERY
        class_q = _JS_CLASS_QUERY
        import_q = _JS_IMPORT_QUERY
        export_func_q = _JS_EXPORT_FUNC_QUERY
        export_default_q = _JS_EXPORT_DEFAULT_QUERY

    _ = lang  # used for grammar selection above

    tree = parser.parse(source)
    root = tree.root_node
    has_errors = _has_tree_errors(root)

    if has_errors:
        logger.warning("JS/TS file has parse errors", path=str(path))

    # Extract functions
    functions = _extract_functions(root, func_q, arrow_q, func_expr_q, export_func_q)

    # Extract classes
    classes = _extract_classes(root, class_q)

    # Extract imports (ES modules)
    imports = _extract_imports(root, import_q)
    # Also collect CommonJS require() calls
    imports = list(imports) + _collect_require_imports(root)

    # Extract exports
    export_names, has_default_export = _extract_exports(root, export_func_q, export_default_q)

    # Detect test patterns
    has_test_patterns = _detect_test_patterns(source)

    return ParsedJavaScriptFile(
        path=str(path),
        language=grammar,
        functions=functions,
        classes=tuple(classes),
        imports=tuple(imports),
        export_names=export_names,
        has_default_export=has_default_export,
        has_test_patterns=has_test_patterns,
        has_errors=has_errors,
    )


def _extract_functions(
    root: Node,
    func_q: Query,
    arrow_q: Query,
    func_expr_q: Query,
    export_func_q: Query,
) -> tuple[ParsedJSFunction, ...]:
    """Extract function declarations, arrow functions, and function expressions."""
    exported_names: set[str] = set()
    export_cursor = QueryCursor(export_func_q)
    export_captures = export_cursor.captures(root)
    for node in export_captures.get("export_func", []):
        exported_names.add(_text(node))

    functions: list[ParsedJSFunction] = []
    seen_names: set[str] = set()

    # Regular function declarations
    cursor = QueryCursor(func_q)
    captures = cursor.captures(root)
    for node in captures.get("func_name", []):
        name = _text(node)
        if name in seen_names:
            continue
        seen_names.add(name)
        func_def = node.parent
        if func_def is None:
            continue
        functions.append(
            ParsedJSFunction(
                name=name,
                line_start=func_def.start_point[0] + 1,
                line_end=func_def.end_point[0] + 1,
                is_arrow=False,
                is_exported=name in exported_names,
            )
        )

    # Arrow functions
    arrow_cursor = QueryCursor(arrow_q)
    arrow_captures = arrow_cursor.captures(root)
    for node in arrow_captures.get("func_name", []):
        name = _text(node)
        if name in seen_names:
            continue
        seen_names.add(name)
        var_decl = node.parent
        if var_decl is None:
            continue
        lex_decl = var_decl.parent
        if lex_decl is None:
            continue
        functions.append(
            ParsedJSFunction(
                name=name,
                line_start=lex_decl.start_point[0] + 1,
                line_end=lex_decl.end_point[0] + 1,
                is_arrow=True,
                is_exported=name in exported_names,
            )
        )

    # Function expressions (const foo = function() {})
    expr_cursor = QueryCursor(func_expr_q)
    expr_captures = expr_cursor.captures(root)
    for node in expr_captures.get("func_name", []):
        name = _text(node)
        if name in seen_names:
            continue
        seen_names.add(name)
        var_decl = node.parent
        if var_decl is None:
            continue
        lex_decl = var_decl.parent
        if lex_decl is None:
            continue
        functions.append(
            ParsedJSFunction(
                name=name,
                line_start=lex_decl.start_point[0] + 1,
                line_end=lex_decl.end_point[0] + 1,
                is_arrow=False,
                is_exported=name in exported_names,
            )
        )

    return tuple(functions)


def _extract_classes(root: Node, class_q: Query) -> list[ParsedJSClass]:
    """Extract class declarations."""
    cursor = QueryCursor(class_q)
    captures = cursor.captures(root)
    classes: list[ParsedJSClass] = []
    for node in captures.get("class_name", []):
        name = _text(node)
        class_def = node.parent
        if class_def is None:
            continue
        extends = _get_extends_clause(class_def)
        classes.append(
            ParsedJSClass(
                name=name,
                line_start=class_def.start_point[0] + 1,
                line_end=class_def.end_point[0] + 1,
                extends=extends,
            )
        )
    return classes


def _extract_imports(root: Node, import_q: Query) -> list[ParsedJSImport]:
    """Extract ES module imports."""
    cursor = QueryCursor(import_q)
    captures = cursor.captures(root)
    imports: list[ParsedJSImport] = []
    for node in captures.get("import_source", []):
        source = _strip_quotes(_text(node))
        imports.append(ParsedJSImport(source=source, is_require=False))
    return imports


def _extract_exports(
    root: Node,
    export_func_q: Query,
    export_default_q: Query,
) -> tuple[tuple[str, ...], bool]:
    """Extract export names and detect default exports."""
    cursor = QueryCursor(export_func_q)
    captures = cursor.captures(root)
    names = [_text(node) for node in captures.get("export_func", [])]

    default_cursor = QueryCursor(export_default_q)
    default_captures = default_cursor.captures(root)
    has_default = len(default_captures.get("default_kw", [])) > 0

    return tuple(names), has_default
