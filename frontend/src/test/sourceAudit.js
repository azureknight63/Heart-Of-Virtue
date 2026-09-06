import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

import * as espree from 'espree'

/**
 * Static audits that need to see the SHAPE of the code, not its behaviour.
 *
 * WHY A PARSER
 * ------------
 * Both audits below ask a question no rendering test can answer, because both
 * are about a defect that is invisible until an input nobody has ever sent
 * arrives. A grep cannot answer them either: `TABLE[k] || fallback` and
 * `arr[i] || 0` are the same characters and only one is a bug, and the
 * difference is what `TABLE` and `arr` were declared as. So the source is
 * parsed and the declarations are read.
 *
 * `espree` is eslint's parser. It reached this file transitively at first,
 * which meant an eslint major bump could take the parser out from under two
 * security audits; it is now a declared devDependency in its own right. Should
 * it ever go missing anyway, these suites fail to IMPORT rather than passing
 * vacuously, which is the right direction to fail in.
 *
 * TWO AUDITS, ONE PARSE
 * ---------------------
 *   {@link findUnguardedTableLookups}    prototype pollution via `table[key]`
 *   {@link findNativeFormSubmissions}    credentials leaving through a native
 *                                        form `action`
 *
 * They share the corpus and the walker and nothing else. Each states its own
 * reach, in its own docstring, including what it does NOT cover — a guard that
 * sounds general and is not is the failure this file is written against.
 */

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), '..')

const SKIP_DIRS = new Set(['node_modules', '__pycache__', 'dist', 'build', 'coverage'])

/**
 * Every shipped `.js`/`.jsx` module under `src`.
 *
 * Test files are excluded: they do not ship, and a fixture deliberately
 * feeding a hostile key to prove a guard works would otherwise be reported as
 * the very defect it is proving. `src/test/` (the shared helpers) goes with
 * them for the same reason.
 *
 * Taking `root` as an argument keeps the scanners falsifiable — the suite runs
 * them over the real tree AND over hand-built sources with a known defect, so
 * a green result is evidence the scan works rather than evidence it looked at
 * nothing.
 */
export function readSourceFiles(root = SRC_DIR) {
    const files = []
    const walk = (dir) => {
        for (const entry of readdirSync(dir, { withFileTypes: true })) {
            const full = join(dir, entry.name)
            if (entry.isDirectory()) {
                if (!SKIP_DIRS.has(entry.name) && entry.name !== 'test') walk(full)
                continue
            }
            if (!/\.jsx?$/.test(entry.name)) continue
            if (/\.test\.jsx?$/.test(entry.name)) continue
            files.push({
                path: relative(root, full).split(sep).join('/'),
                content: readFileSync(full, 'utf8'),
            })
        }
    }
    walk(root)
    return files
}

const parse = (source) => espree.parse(source, {
    ecmaVersion: 'latest',
    sourceType: 'module',
    loc: true,
    ecmaFeatures: { jsx: true },
})

/** Depth-first walk over every AST node, recording each node's parent. */
function walkAst(root, visit) {
    const parents = new Map()
    const step = (node, parent) => {
        parents.set(node, parent)
        visit(node, parent, parents)
        for (const key of Object.keys(node)) {
            if (key === 'loc' || key === 'range') continue
            const value = node[key]
            if (Array.isArray(value)) {
                for (const child of value) {
                    if (child && typeof child.type === 'string') step(child, node)
                }
            } else if (value && typeof value.type === 'string') {
                step(value, node)
            }
        }
    }
    step(root, null)
    return parents
}

/** Parse every file, dropping (and naming) any the parser rejects. */
function parseAll(files) {
    const asts = new Map()
    const unparsed = []
    for (const { path, content } of files) {
        try {
            asts.set(path, parse(content))
        } catch (error) {
            unparsed.push(`${path}: ${error.message}`)
        }
    }
    return { asts, unparsed }
}

// ---------------------------------------------------------------------------
// Audit 1 — prototype-unsafe lookup tables
// ---------------------------------------------------------------------------

/**
 * Whether an object literal is a LOOKUP TABLE: every property a plain, static
 * key. A spread, a computed key or a method makes it something else — a props
 * bag, a config being merged — and reading it with a dynamic key is not the
 * pattern this audit is about.
 */
function isLookupTable(node) {
    return node
        && node.type === 'ObjectExpression'
        && node.properties.length > 0
        && node.properties.every((p) => (
            p.type === 'Property' && !p.computed
            && (p.key.type === 'Identifier' || p.key.type === 'Literal')
        ))
}

/** `Object.fromEntries(...)` — a lookup table built rather than written. */
function isBuiltTable(node) {
    return node
        && node.type === 'CallExpression'
        && node.callee.type === 'MemberExpression'
        && !node.callee.computed
        && node.callee.object.type === 'Identifier'
        && node.callee.object.name === 'Object'
        && node.callee.property.type === 'Identifier'
        && node.callee.property.name === 'fromEntries'
}

/**
 * The dotted paths under a table root that are themselves tables: `''` for the
 * root, plus `border`, `text.muted` and so on for nested literals. This is
 * what lets the audit see `colors.border[variant]`, not just `TABLE[key]`.
 */
function tablePaths(node, prefix = '', found = new Set()) {
    found.add(prefix)
    if (!isLookupTable(node)) return found
    for (const property of node.properties) {
        if (!isLookupTable(property.value)) continue
        const name = property.key.type === 'Identifier'
            ? property.key.name
            : String(property.key.value)
        tablePaths(property.value, prefix ? `${prefix}.${name}` : name, found)
    }
    return found
}

/** `export const NAME = {...}` per module — the tables another file can import. */
function exportedTables(asts) {
    const byModule = new Map()
    for (const [path, ast] of asts) {
        const tables = new Map()
        for (const node of ast.body) {
            if (node.type !== 'ExportNamedDeclaration' || !node.declaration) continue
            if (node.declaration.type !== 'VariableDeclaration') continue
            for (const declarator of node.declaration.declarations) {
                if (declarator.id.type !== 'Identifier') continue
                if (isLookupTable(declarator.init)) {
                    tables.set(declarator.id.name, tablePaths(declarator.init))
                } else if (isBuiltTable(declarator.init)) {
                    tables.set(declarator.id.name, new Set(['']))
                }
            }
        }
        if (tables.size) byModule.set(path, tables)
    }
    return byModule
}

/** A relative specifier resolved to a path in the corpus, or `null`. */
function resolveSpecifier(fromPath, specifier, asts) {
    if (!specifier.startsWith('.')) return null
    const base = resolve(dirname(join(SRC_DIR, fromPath)), specifier)
    const candidates = [
        base, `${base}.js`, `${base}.jsx`, join(base, 'index.js'), join(base, 'index.jsx'),
    ]
    for (const candidate of candidates) {
        const rel = relative(SRC_DIR, candidate).split(sep).join('/')
        if (asts.has(rel)) return rel
    }
    return null
}

/** Every lookup-table name in scope in one module: declared here, or imported. */
function tablesVisibleIn(path, ast, exported, asts) {
    const tables = new Map()
    walkAst(ast, (node) => {
        if (node.type !== 'VariableDeclarator' || node.id.type !== 'Identifier') return
        if (isLookupTable(node.init)) tables.set(node.id.name, tablePaths(node.init))
        else if (isBuiltTable(node.init)) tables.set(node.id.name, new Set(['']))
    })
    for (const node of ast.body) {
        if (node.type !== 'ImportDeclaration') continue
        const target = resolveSpecifier(path, node.source.value, asts)
        const fromModule = target && exported.get(target)
        if (!fromModule) continue
        for (const specifier of node.specifiers) {
            if (specifier.type !== 'ImportSpecifier') continue
            const paths = fromModule.get(specifier.imported.name)
            if (paths) tables.set(specifier.local.name, paths)
        }
    }
    return tables
}

/** A computed member expression's receiver, as `rootName` + a dotted path. */
function receiverOf(node) {
    let current = node.object
    const parts = []
    while (
        current.type === 'MemberExpression' && !current.computed
        && current.property.type === 'Identifier'
    ) {
        parts.unshift(current.property.name)
        current = current.object
    }
    return current.type === 'Identifier'
        ? { root: current.name, path: parts.join('.') }
        : null
}

/**
 * Every `table[key] || fallback` still left in the source.
 *
 * WHAT IT COVERS
 * --------------
 * A read is reported when all four hold:
 *   1. the receiver resolves to an object literal (or `Object.fromEntries`)
 *      bound to a `const`/`let` in the same module, or imported by name from
 *      one that exports it — INCLUDING a nested path like `colors.border`;
 *   2. the key is not a literal, so it is dynamic and could be `constructor`;
 *   3. the read is the LEFT operand of `||` or `??` — the fallback shape;
 *   4. nothing else. There is no exemption list, so a fourth site added
 *      tomorrow is reported without anybody remembering to register it.
 *
 * WHAT IT DOES NOT COVER, SAID PLAINLY
 * ------------------------------------
 *   - a table that is not an object literal at its declaration: a `useRef({})`
 *     bag, a value from JSON, a function parameter (`mapEmotion(table, key)`
 *     in hooks/useNpcChat.js is exactly this). Those were fixed by hand and
 *     nothing here holds them fixed.
 *   - a table imported through a re-export barrel, or under a namespace
 *     import (`import * as theme`). Only a direct named import is followed.
 *   - the fallback written any other way: `const v = T[k]` then `v || x` two
 *     lines later, `T[k] ? a : b`, `!T[k]`. Only the `||`/`??` shape is
 *     reported, because that is the shape whose fallback is silently defeated
 *     — the ternary and the negation are wrong in the same way, but they were
 *     not what the codebase was actually written in, and widening the pattern
 *     to shapes with no occurrences buys reach that cannot be demonstrated.
 *   - shadowing. A local named `colors` inside a function is treated as the
 *     imported table. This over-reports rather than under-reports.
 *
 * @param {Array<{path: string, content: string}>} files
 * @returns {{findings: Array, tableCount: number, unparsed: Array<string>}}
 *   `findings` are `{where, line, receiver}`; `tableCount` is how many table
 *   bindings the scan actually resolved, so a suite can refuse to call a scan
 *   that found nothing a pass.
 */
export function findUnguardedTableLookups(files) {
    const { asts, unparsed } = parseAll(files)
    const exported = exportedTables(asts)
    const findings = []
    let tableCount = 0

    for (const { path } of files) {
        const ast = asts.get(path)
        if (!ast) continue
        const tables = tablesVisibleIn(path, ast, exported, asts)
        tableCount += tables.size
        walkAst(ast, (node, parent, parents) => {
            if (node.type !== 'MemberExpression' || !node.computed) return
            if (node.property.type === 'Literal') return
            const receiver = receiverOf(node)
            if (!receiver) return
            const paths = tables.get(receiver.root)
            if (!paths || !paths.has(receiver.path)) return
            // Step past an optional-chaining wrapper so `a?.[k] || b` is seen,
            // carrying the wrapper along as the operand to compare against —
            // otherwise `a?.b || TABLE[k]` reads as a left operand it is not.
            let operand = node
            let enclosing = parent
            while (enclosing && enclosing.type === 'ChainExpression') {
                operand = enclosing
                enclosing = parents.get(enclosing)
            }
            if (!enclosing || enclosing.type !== 'LogicalExpression') return
            if (enclosing.operator !== '||' && enclosing.operator !== '??') return
            if (enclosing.left !== operand) return
            findings.push({
                where: path,
                line: node.loc.start.line,
                receiver: receiver.path ? `${receiver.root}.${receiver.path}` : receiver.root,
            })
        })
    }
    return { findings, tableCount, unparsed }
}

// ---------------------------------------------------------------------------
// Audit 2 — native form submission
// ---------------------------------------------------------------------------

/** Attributes that make a `<form>` submit itself through the browser. */
const NATIVE_SUBMIT_ATTRIBUTES = new Set(['action', 'method'])

/**
 * Every `<form>` in the source that carries a native `action` or `method`.
 *
 * A React form whose submission is a JS handler does not need either, and
 * carrying them is not inert: they are precisely what the browser falls back
 * to when the handler does not run — a throw before `preventDefault()`, a
 * chunk that failed to load, an extension that broke the bundle. For the login
 * form that fallback posted the player's username and password to a path that
 * is a client-side route and no server endpoint.
 *
 * COVERS every `<form>` element in every shipped module, with no exemption
 * list. DOES NOT cover a form rendered by `React.createElement('form', …)`, a
 * form whose attributes are spread in from an object, or a `<form>` in a
 * component library under `node_modules`. If a form ever genuinely needs a
 * native action, this audit is the place to record why — as a check on the
 * attribute's VALUE rather than a name added to a skip list.
 *
 * @param {Array<{path: string, content: string}>} files
 * @returns {{findings: Array, formCount: number, unparsed: Array<string>}}
 */
export function findNativeFormSubmissions(files) {
    const { asts, unparsed } = parseAll(files)
    const findings = []
    let formCount = 0

    for (const { path } of files) {
        const ast = asts.get(path)
        if (!ast) continue
        walkAst(ast, (node) => {
            if (node.type !== 'JSXOpeningElement') return
            if (node.name.type !== 'JSXIdentifier' || node.name.name !== 'form') return
            formCount += 1
            for (const attribute of node.attributes) {
                if (attribute.type !== 'JSXAttribute') continue
                if (attribute.name.type !== 'JSXIdentifier') continue
                if (!NATIVE_SUBMIT_ATTRIBUTES.has(attribute.name.name)) continue
                findings.push({
                    where: path,
                    line: attribute.loc.start.line,
                    attribute: attribute.name.name,
                })
            }
        })
    }
    return { findings, formCount, unparsed }
}
