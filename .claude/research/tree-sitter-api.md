# tree-sitter v0.25+ API Research (Verified 2026-03-18)

**Packages**: `tree-sitter` >= 0.25.0, `tree-sitter-language-pack` >= 0.13.0 (165+ grammars, pre-compiled wheels).

## BREAKING CHANGE in v0.25: QueryCursor

Query execution moved from `Query` to `QueryCursor`. The old `query.captures()` / `query.matches()` are REMOVED.

## Loading Languages

```python
from tree_sitter_language_pack import get_language, get_parser

language = get_language("python")  # returns tree_sitter.Language
parser = get_parser("python")      # returns tree_sitter.Parser (pre-configured)
```

## Parsing

```python
tree = parser.parse(source_bytes)  # source must be bytes
root = tree.root_node
root.type          # "module"
root.text          # bytes
root.start_point   # (row, col)
root.children      # list[Node]
root.child_by_field_name("name")  # field access
str(root)          # S-expression (replaces deprecated .sexp())
```

## Queries (v0.25+ API)

```python
from tree_sitter import Query, QueryCursor

query = Query(language, '(function_definition name: (identifier) @func_name)')
cursor = QueryCursor(query)

# captures: flat dict of all captures
captures = cursor.captures(tree.root_node)  # dict[str, list[Node]]
for node in captures.get("func_name", []):
    print(node.text.decode("utf8"))

# matches: grouped by pattern
matches = cursor.matches(tree.root_node)  # list[tuple[int, dict[str, list[Node]]]]
```

## Useful Predicates

`#match?`, `#not-match?`, `#eq?`, `#not-eq?`, `#any-of?`, `#not-any-of?`

```scm
(function_definition name: (identifier) @test_func
  (#match? @test_func "^test_"))
```

## Node.text is bytes

Always decode: `node.text.decode("utf8")`.
