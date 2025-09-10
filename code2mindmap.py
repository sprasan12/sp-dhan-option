#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, sys, ast, argparse, html
from typing import List, Dict, Any, Optional

DEFAULT_EXCLUDE_DIRS = {'.git', 'node_modules', 'dist', 'build', '__pycache__', '.venv', 'venv', '.idea', '.vscode', 'target', 'out', '.next', '.nuxt'}
DEFAULT_EXTS = {'.py', '.js', '.ts', '.java', '.go', '.rb', '.cs'}

# ---------- Simple tree model ----------
class Node:
    def __init__(self, name: str, kind: str, path: str = "", meta: Optional[Dict[str, Any]] = None):
        self.name = name
        self.kind = kind  # 'dir' | 'file' | 'sym'
        self.path = path
        self.children: List["Node"] = []
        self.meta = meta or {}

    def add(self, child: "Node"):
        self.children.append(child)

# ---------- Language parsers ----------
def parse_python_symbols(source: str) -> List[Node]:
    try:
        tree = ast.parse(source)
    except Exception:
        return []
    symbols: List[Node] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            cls = Node(node.name, 'sym', meta={'lang':'python','sym':'class'})
            # public methods
            for b in node.body:
                if isinstance(b, ast.FunctionDef) and not b.name.startswith('_'):
                    cls.add(Node(b.name + "()", 'sym', meta={'lang':'python','sym':'method'}))
            symbols.append(cls)
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
            symbols.append(Node(node.name + "()", 'sym', meta={'lang':'python','sym':'function'}))
    return symbols

JS_FUNC_RE = re.compile(r'\bfunction\s+([A-Za-z_]\w*)\s*\(', re.MULTILINE)
JS_CLASS_RE = re.compile(r'\bclass\s+([A-Za-z_]\w*)\b', re.MULTILINE)
JS_ARROW_RE = re.compile(r'\bconst\s+([A-Za-z_]\w*)\s*=\s*\([^)]*\)\s*=>', re.MULTILINE)
JS_EXPORT_FUNC_RE = re.compile(r'\bexport\s+default\s+function\s+([A-Za-z_]\w*)\s*\(', re.MULTILINE)

def parse_js_ts_symbols(source: str) -> List[Node]:
    syms: List[Node] = []
    for name in JS_CLASS_RE.findall(source):
        syms.append(Node(name, 'sym', meta={'lang':'js/ts','sym':'class'}))
    for name in JS_FUNC_RE.findall(source):
        syms.append(Node(name + "()", 'sym', meta={'lang':'js/ts','sym':'function'}))
    for name in JS_ARROW_RE.findall(source):
        syms.append(Node(name + "()", 'sym', meta={'lang':'js/ts','sym':'function'}))
    for name in JS_EXPORT_FUNC_RE.findall(source):
        syms.append(Node(name + "()", 'sym', meta={'lang':'js/ts','sym':'function'}))
    return dedupe_syms(syms)

JAVA_TYPE_RE = re.compile(r'\b(class|interface|enum)\s+([A-Za-z_]\w*)\b', re.MULTILINE)
JAVA_METHOD_RE = re.compile(r'\bpublic\s+(?:static\s+)?[A-Za-z_<>\[\]]+\s+([A-Za-z_]\w*)\s*\(', re.MULTILINE)

def parse_java_symbols(source: str) -> List[Node]:
    syms: List[Node] = []
    for kind, name in JAVA_TYPE_RE.findall(source):
        node = Node(name, 'sym', meta={'lang':'java','sym':kind})
        # attach public methods under the type (shallow)
        methods = JAVA_METHOD_RE.findall(source)
        for m in sorted(set(methods)):
            node.add(Node(m + "()", 'sym', meta={'lang':'java','sym':'method'}))
        syms.append(node)
    return syms

def dedupe_syms(nodes: List[Node]) -> List[Node]:
    seen = set()
    out = []
    for n in nodes:
        k = (n.name, n.meta.get('lang'), n.meta.get('sym'))
        if k not in seen:
            seen.add(k)
            out.append(n)
    return out

def parse_symbols_for_file(path: str, ext: str) -> List[Node]:
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            src = f.read()
    except Exception:
        return []
    if ext == '.py':
        return parse_python_symbols(src)
    if ext in ('.js', '.ts'):
        return parse_js_ts_symbols(src)
    if ext == '.java':
        return parse_java_symbols(src)
    # light/no parsing for other languages; just show file
    return []

# ---------- Scanner ----------
def build_tree(root_dir: str, include_exts: set, exclude_dirs: set, max_depth: int, max_files_per_dir: int) -> Node:
    root = Node(os.path.basename(os.path.abspath(root_dir)) or root_dir, 'dir', path=root_dir)

    def _scan(cur: Node, cur_path: str, depth: int):
        if depth > max_depth:
            return
        try:
            entries = list(os.scandir(cur_path))
        except Exception:
            return

        dirs = [e for e in entries if e.is_dir(follow_symlinks=False)]
        files = [e for e in entries if e.is_file(follow_symlinks=False)]
        # Directories
        for d in sorted(dirs, key=lambda e: e.name)[:1000]:
            if d.name in exclude_dirs or d.name.startswith('.'):
                continue
            child = Node(d.name, 'dir', path=d.path)
            cur.add(child)
            _scan(child, d.path, depth + 1)

        # Files
        shown = 0
        for f in sorted(files, key=lambda e: e.name):
            if shown >= max_files_per_dir:
                break
            ext = os.path.splitext(f.name)[1].lower()
            if ext and include_exts and ext not in include_exts:
                continue
            file_node = Node(f.name, 'file', path=f.path, meta={'ext': ext})
            # Parse symbols for known languages
            syms = parse_symbols_for_file(f.path, ext)
            for s in syms:
                file_node.add(s)
            cur.add(file_node)
            shown += 1

    _scan(root, root_dir, 0)
    return root

# ---------- Mermaid (mindmap) ----------
def to_mermaid_mindmap(root: Node) -> str:
    lines = ["```mermaid", "mindmap", f"  root(({root.name}))"]

    def esc(label: str) -> str:
        # Mermaid is fine with most chars; keep it simple
        return label.replace('`','\\`')

    def icon(node: Node) -> str:
        if node.kind == 'dir': return "📁 "
        if node.kind == 'file': return "📄 "
        sym = node.meta.get('sym')
        if sym == 'class': return "🏷️ "
        if sym == 'interface': return "🧩 "
        if sym == 'enum': return "🔢 "
        if sym in ('function','method'): return "ƒ "
        return ""

    def walk(node: Node, indent: int, prefix: str = "  "):
        for ch in node.children:
            label = icon(ch) + ch.name
            lines.append(f"{'  '*(indent+1)}{prefix}{esc(label)}")
            walk(ch, indent + 1, prefix)

    walk(root, 0)
    lines.append("```")
    return "\n".join(lines)

# ---------- FreeMind (.mm XML) ----------
def to_freemind(root: Node) -> str:
    def node_xml(n: Node, level=0) -> str:
        text = html.escape(n.name)
        parts = [f'{"  "*(level)}<node TEXT="{text}">']
        for c in n.children:
            parts.append(node_xml(c, level+1))
        parts.append(f'{"  "*(level)}</node>')
        return "\n".join(parts)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<map version="1.0.1">
{node_xml(root)}
</map>
""".strip()

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Scan a codebase and generate a mindmap (Mermaid + FreeMind).")
    ap.add_argument("--root", required=True, help="Path to project root")
    ap.add_argument("--out-mermaid", default="codebase_mindmap.md", help="Output .md with Mermaid mindmap")
    ap.add_argument("--out-freemind", default="codebase_mindmap.mm", help="Output FreeMind .mm file")
    ap.add_argument("--include-ext", default=",".join(sorted(DEFAULT_EXTS)),
                    help="Comma-separated file extensions to include (e.g. .py,.js,.ts,.java)")
    ap.add_argument("--exclude-dirs", default=",".join(sorted(DEFAULT_EXCLUDE_DIRS)),
                    help="Comma-separated directory names to exclude")
    ap.add_argument("--max-depth", type=int, default=8, help="Max directory depth to scan")
    ap.add_argument("--max-files-per-dir", type=int, default=500, help="Limit files per directory")
    args = ap.parse_args()

    include_exts = {e.strip().lower() if e.strip().startswith('.') else '.'+e.strip().lower()
                    for e in args.include_ext.split(',') if e.strip()}
    exclude_dirs = {d.strip() for d in args.exclude_dirs.split(',') if d.strip()}

    tree = build_tree(args.root, include_exts, exclude_dirs, args.max_depth, args.max_files_per_dir)

    mermaid = to_mermaid_mindmap(tree)
    with open(args.out_mermaid, 'w', encoding='utf-8') as f:
        f.write(mermaid)

    freemind = to_freemind(tree)
    with open(args.out_freemind, 'w', encoding='utf-8') as f:
        f.write(freemind)

    print(f"✅ Mermaid mindmap: {args.out_mermaid}")
    print(f"✅ FreeMind map   : {args.out_freemind}")

if __name__ == "__main__":
    main()
