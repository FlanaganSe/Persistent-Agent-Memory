"""Unit tests for the JavaScript/TypeScript tree-sitter parser."""

from __future__ import annotations

from pathlib import Path

from rkp.indexer.parsers.javascript import parse_javascript_file


class TestParseJavaScriptFile:
    def test_extract_js_functions(self) -> None:
        source = b"""
function greet(name) {
    return "Hello, " + name;
}

function add(a, b) {
    return a + b;
}
"""
        result = parse_javascript_file(Path("test.js"), source=source)
        assert len(result.functions) == 2
        names = {f.name for f in result.functions}
        assert "greet" in names
        assert "add" in names
        assert result.language == "javascript"

    def test_extract_arrow_functions(self) -> None:
        source = b"""
const foo = () => {
    return 42;
};

const bar = (x) => x * 2;
"""
        result = parse_javascript_file(Path("test.js"), source=source)
        arrows = [f for f in result.functions if f.is_arrow]
        assert len(arrows) >= 1
        arrow_names = {f.name for f in arrows}
        assert "foo" in arrow_names
        for arrow in arrows:
            assert arrow.is_arrow is True

    def test_extract_classes(self) -> None:
        source = b"""
class Foo extends Bar {
    constructor() {
        super();
    }

    doStuff() {
        return true;
    }
}

class Baz {
    hello() {}
}
"""
        result = parse_javascript_file(Path("test.js"), source=source)
        assert len(result.classes) == 2

        class_names = {c.name for c in result.classes}
        assert "Foo" in class_names
        assert "Baz" in class_names

        baz_cls = next(c for c in result.classes if c.name == "Baz")
        assert baz_cls.extends is None

    def test_extract_imports(self) -> None:
        source = b"""
import React from 'react';
import { useState, useEffect } from 'react';
import * as path from 'path';
"""
        result = parse_javascript_file(Path("test.js"), source=source)
        assert len(result.imports) >= 3
        sources = {i.source for i in result.imports}
        assert "react" in sources
        assert "path" in sources
        for imp in result.imports:
            assert imp.is_require is False

    def test_extract_require(self) -> None:
        source = b"""
const fs = require('fs');
const path = require('path');
"""
        result = parse_javascript_file(Path("test.js"), source=source)
        require_imports = [i for i in result.imports if i.is_require]
        assert len(require_imports) >= 2
        sources = {i.source for i in require_imports}
        assert "fs" in sources
        assert "path" in sources
        for imp in require_imports:
            assert imp.is_require is True

    def test_detect_test_patterns(self) -> None:
        source = b"""
describe('MyModule', () => {
    it('should do something', () => {
        expect(true).toBe(true);
    });

    test('another test', () => {
        expect(1 + 1).toBe(2);
    });
});
"""
        result = parse_javascript_file(Path("test.js"), source=source)
        assert result.has_test_patterns is True

    def test_typescript_parsing(self) -> None:
        source = b"""
function greet(name: string): string {
    return "Hello, " + name;
}

interface User {
    id: number;
    name: string;
}

const add = (a: number, b: number): number => a + b;
"""
        result = parse_javascript_file(Path("test.ts"), source=source)
        assert result.language == "typescript"
        func_names = {f.name for f in result.functions}
        assert "greet" in func_names

    def test_parse_errors_graceful(self) -> None:
        source = b"function {{{ broken @@@ syntax ))) \n class \n"
        result = parse_javascript_file(Path("broken.js"), source=source)
        assert result.has_errors is True
        # Should still return a result, not crash
        assert result.path == "broken.js"

    def test_empty_file(self) -> None:
        result = parse_javascript_file(Path("empty.js"), source=b"")
        assert result.functions == ()
        assert result.classes == ()
        assert result.imports == ()
        assert result.export_names == ()
        assert result.has_default_export is False
        assert result.has_test_patterns is False

    def test_exports(self) -> None:
        source = b"""
export function publicFunc() {
    return 1;
}

function privateFunc() {
    return 2;
}

export default function main() {
    return 3;
}
"""
        result = parse_javascript_file(Path("test.js"), source=source)
        assert "publicFunc" in result.export_names
        assert result.has_default_export is True
        # Verify exported function is marked as exported
        public = next(f for f in result.functions if f.name == "publicFunc")
        assert public.is_exported is True

    def test_no_test_patterns(self) -> None:
        source = b"""
function compute(x) {
    return x * 2;
}
"""
        result = parse_javascript_file(Path("test.js"), source=source)
        assert result.has_test_patterns is False

    def test_mixed_imports(self) -> None:
        """ES module and CommonJS imports are both captured."""
        source = b"""
import lodash from 'lodash';
const express = require('express');
"""
        result = parse_javascript_file(Path("test.js"), source=source)
        assert len(result.imports) == 2
        es_imports = [i for i in result.imports if not i.is_require]
        cjs_imports = [i for i in result.imports if i.is_require]
        assert len(es_imports) == 1
        assert es_imports[0].source == "lodash"
        assert len(cjs_imports) == 1
        assert cjs_imports[0].source == "express"
