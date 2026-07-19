#!/usr/bin/env nu
#
# Script to make sure file path in `Gtk.Template.from_resource` in accordance with files under "src/ui/" folder.
#
# For example, if in Python code, we have:
# ```py
# @Gtk.Template.from_resource("/vn/hoabinh/quan/CoBang/gtk/scanner-page.ui")
# ```
#
# We strip the application prefix `/vn/hoabinh/quan/CoBang/` to get the project-scoped path "gtk/scanner-page.ui".
# Those `gtk/**/*.ui` files are compiled from `src/ui/**/*.blp` files (see `blueprints` target in _meson.build_),
# so make sure _src/ui/scanner-page.blp_ exists.
#
# Also make sure:
# - The _*.ui_ file is mentioned in `src/cobang.gresource.xml`
# - The _*.blp_ file is mentioned in the `blueprints = custom_target("blueprints", input: files( ... ))` block of _src/meson.build_ file.
#
# The script also reports the reverse direction: every `*.blp` file under `src/ui/`
# must be listed in the `blueprints` target of `src/meson.build`, and every compiled
# `*.ui` file referenced from `src/cobang.gresource.xml` must have a backing `*.blp` source.
#
# Exit code:
#   0  - everything is consistent
#   1  - one or more inconsistencies were found

# Application prefix that GResource adds to every bundled path.
# Change this constant if the Flatpak/Desktop id ever changes.
const APP_RES_PREFIX = "/vn/hoabinh/quan/CoBang"
const APP_RES_PREFIX_SLASH = "/vn/hoabinh/quan/CoBang/"

# Paths of the files we inspect, relative to the project root.
const PY_GLOB = "src/**/*.py"
const GRESOURCE_XML = "src/cobang.gresource.xml"
const SRC_MESON = "src/meson.build"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Resolve the project root (the parent of the `dev/` folder this script lives in).
# `path self` is resolved at parse time, so it correctly reflects the location of
# this script regardless of how it is invoked (direct shebang, source, or use).
const PROJECT_ROOT = (path self | path dirname | path dirname)

# All Python source files we may want to scan for `@Gtk.Template.from_resource` decorators.
def python-sources [] {
    glob ($PROJECT_ROOT | path join $PY_GLOB)
}

# Extract every `@Gtk.Template.from_resource("/...")` call from a Python file
# and return one record per occurrence with the absolute Python file path and the
# full resource path passed to the constructor.
def template-resource-refs [py_file: string] {
    let pattern = r#'@Gtk\.Template\.from_resource\(\s*["'']([^"'']+)["'']\s*\)'#
    open --raw $py_file
    | lines
    | enumerate
    | each { |row|
        let line_no = $row.index + 1
        let line = $row.item
        let matches = ($line | parse --regex $pattern)
        if ($matches | is-empty) {
            []
        } else {
            $matches | each { |m| { py_file: $py_file, line: $line_no, resource: ($m.capture0 | into string) } }
        }
    }
    | flatten
}

# Given the absolute path to a Python file, find all `@Gtk.Template.from_resource(...)`
# references it contains, validated as being under our application prefix.
def references-in-py [py_file: string] {
    template-resource-refs $py_file
    | each { |ref|
        let project = $ref.resource
        if not ($project | str starts-with $APP_RES_PREFIX_SLASH) {
            error make { msg: $"Resource path \"($ref.resource)\" in ($ref.py_file | path relative-to $PROJECT_ROOT) line ($ref.line) is not under app prefix ($APP_RES_PREFIX)" }
        }
        let prefix_len = ($APP_RES_PREFIX_SLASH | str length)
        let ui_rel = ($project | str substring $prefix_len..)
        {
            py_file: $ref.py_file,
            line: $ref.line,
            resource: $ref.resource,
            ui_rel: $ui_rel,
        }
    }
}

# Map a project-relative compiled `gtk/.../*.ui` path back to the `src/ui/...*.blp` source.
# The blueprints target output is `gtk/`, mirroring the layout of `src/ui/`.
def ui-to-blp [ui_rel: string] {
    if not ($ui_rel | str starts-with "gtk/") {
        error make { msg: $"Resource path \"($ui_rel)\" is not under the \"gtk/\" output directory" }
    }
    let stripped = $ui_rel | str substring 4..   # drop "gtk/"
    let new_path = ($stripped | path parse --extension ui | update extension blp | path join)
    $"src/ui/($new_path)"
}

# Read the `<file ...>...</file>` lines from gresource.xml and return every
# (alias-or-nothing, real_path) pair, ignoring the `preprocess=` attribute.
def gresource-files [gresource_xml: string] {
    let file_pattern = r#'<file\b([^>]*)>([^<]+)</file>'#
    open --raw $gresource_xml
    | lines
    | each { |line|
        let m = ($line | parse --regex $file_pattern)
        if ($m | is-empty) {
            []
        } else {
            $m | each { |hit|
                let attrs = $hit.capture0
                let real = ($hit.capture1 | str trim)
                let alias_match = ($attrs | parse --regex r#'alias\s*=\s*"([^"]+)"'#)
                let alias_path = if ($alias_match | is-empty) { "" } else { $alias_match.0.capture0 }
                { alias_path: $alias_path, real: $real }
            }
        }
    }
    | flatten
}

# Collect every `.blp` file listed under the
# `blueprints = custom_target("blueprints", input: files( ... ))` block of `src/meson.build`.
# The block is found with a multiline regex that captures everything between
# `input: files(` and the matching `)`.
def blueprint-inputs [meson_file: string] {
    let body = (open --raw $meson_file)
    let parsed = ($body | parse --regex r#'(?ms)input:\s+files\((.*?)\)'#)
    if ($parsed | is-empty) {
        return []
    }
    $parsed
    | get capture0.0
    | str trim
    | lines
    | each { |line|
        $line | parse --regex r#'['"]([^'"]+\.blp)['"]'#
    }
    | flatten
    | get capture0
}

# Extract dynamic class names declared in a `.blp` file.
# In Blueprint, dynamic object classes are written as `$ClassName`:
#   template $ScannerPage: Adw.Bin { ... }
#   child: $ScannerPage scanner_page { ... };
# This returns the unique class names declared by `template $...` and by
# references `$ClassName id { ... }`.
def dynamic-classes [blp_file: string] {
    let body = (open --raw $blp_file)
    let template_pattern = r#'template\s+\$([A-Za-z][A-Za-z0-9_]*)'#
    let ref_pattern = r#'(?<!template\s)\$([A-Za-z][A-Za-z0-9_]*)'#
    let template_hits = ($body | parse --regex $template_pattern | get capture0)
    let ref_hits = ($body | parse --regex $ref_pattern | get capture0)
    ($template_hits | append $ref_hits | uniq)
}

# Find all Python classes that have a `@Gtk.Template.from_resource(...)` decorator
# and return a record with the class name, Python file path, and resource path.
def py-template-classes [] {
    let pattern = r#'@Gtk\.Template\.from_resource\(\s*["'']([^"'']+)["'']\s*\)\s*\n\s*class\s+([A-Za-z][A-Za-z0-9_]*)'#
    python-sources
    | each { |py_file|
        let body = (open --raw $py_file)
        let hits = ($body | parse --regex $pattern)
        if ($hits | is-empty) {
            []
        } else {
            $hits | each { |m|
                {
                    py_file: $py_file,
                    class_name: ($m.capture1 | into string),
                    resource: ($m.capture0 | into string),
                }
            }
        }
    }
    | flatten
}

# Convert a class name to the expected project-relative compiled *.ui path.
# Blueprint output mirrors the `src/ui/` tree under `gtk/`, and the file name
# is derived from the blp file name (kebab-case), not the class name.
def expected-ui-for-blp [blp_rel: string] {
    let parsed = ($blp_rel | path parse)
    let stem = $parsed.stem
    let parent = ($parsed.parent | str replace "src/ui/" "")
    if $parent == "" {
        $"gtk/($stem).ui"
    } else {
        $"gtk/($parent)/($stem).ui"
    }
}

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

# Pretty-printer: write a status line.
# `parts` is a list of `{text: string, italic: bool}` records. Plain text is
# emitted as-is; parts marked `italic: true` are wrapped in italic-on /
# italic-off ANSI codes. Using explicit segments (rather than post-hoc
# substring replacement) avoids any chance of one path token accidentally
# being matched inside another, and keeps the rendering intent local to each
# call site.
def report [
    ok: bool,
    parts: list<record<text: string, italic: bool>>,
] {
    let rendered = (
        $parts
        | each { |p|
            if $p.italic {
                $"(ansi i)(ansi d)($p.text)(ansi rst)"
            } else {
                $p.text
            }
        }
        | str join ""
    )
    if $ok {
        let ok_label = $"(ansi green)OK(ansi reset)"
        print --stderr $"  ($ok_label)   ($rendered)"
    } else {
        print --stderr $"  FAIL ($rendered)"
    }
}

# Convenience: build a plain text part.
def plain [text: string] { { text: $text, italic: false } }

# Convenience: build an italic part (used to highlight file paths).
def path-style [text: string] { { text: $text, italic: true } }

# Section header.
def section [title: string] {
    print --stderr ""
    print --stderr $"(ansi bo)($title)(ansi rst_bo)"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main [] {
    let root = $PROJECT_ROOT
    cd $root

    let refs = (
        python-sources
        | each { |f| references-in-py $f }
        | flatten
    )

    let gresource_xml = ($root | path join $GRESOURCE_XML)
    let src_meson = ($root | path join $SRC_MESON)
    let g_resources = gresource-files $gresource_xml
    let blueprint_files = (blueprint-inputs $src_meson | each { |p| $"src/($p)" })

    let gresource_paths = ($g_resources | get real)
    let gresource_aliases = ($g_resources | where { |r| $r.alias_path != "" } | get alias_path)
    let gresource_set = ($gresource_paths | append $gresource_aliases)
    let blueprint_set = $blueprint_files

    let on_disk_blps = (glob ($root | path join "src/ui/**/*.blp")
        | each { |p| $p | path relative-to $root })

    let py_classes = (py-template-classes)
    let class_to_resource = ($py_classes | group-by class_name | items { |k, v| { $k: ($v.resource | first) } } | into record)

    mut issues = 0

    section "1. Gtk.Template.from_resource references in Python"
    if ($refs | is-empty) {
        print --stderr "  (no references found)"
    } else {
        for ref in $refs {
            let py_rel = $ref.py_file | path relative-to $root
            let blp_rel = (ui-to-blp $ref.ui_rel)
            let blp_abs = ($root | path join $blp_rel)

            let has_blp = ($blp_abs | path exists)
            report $has_blp [
                (path-style $py_rel) (plain $":($ref.line) -> ") (path-style $ref.resource) (plain " -- backing source ") (path-style $blp_rel)
            ]
            if not $has_blp { $issues = $issues + 1 }

            let in_gresource = ($ref.ui_rel in $gresource_set)
            report $in_gresource [
                (path-style $py_rel) (plain $":($ref.line) -> ") (path-style $ref.resource) (plain " -- bundled in cobang.gresource.xml")
            ]
            if not $in_gresource { $issues = $issues + 1 }

            let in_blueprints = ($blp_rel in $blueprint_set)
            report $in_blueprints [
                (path-style $py_rel) (plain $":($ref.line) -> ") (path-style $ref.resource) (plain " -- listed in blueprints target of src/meson.build")
            ]
            if not $in_blueprints { $issues = $issues + 1 }
        }
    }

    section "2. Every src/ui/**/*.blp must be listed in the blueprints target"
    for blp in $on_disk_blps {
        let listed = ($blp in $blueprint_set)
        report $listed [(path-style $blp)]
        if not $listed { $issues = $issues + 1 }
    }

    section "3. Every compiled *.ui in cobang.gresource.xml must have a *.blp source"
    for res in $g_resources {
        if not ($res.real | str ends-with ".ui") {
            continue
        }
        let blp_rel = (ui-to-blp $res.real)
        let blp_abs = ($root | path join $blp_rel)
        let exists = ($blp_abs | path exists)
        let what_parts = if $res.alias_path != "" {
            [(path-style $res.real) (plain " [as] ") (path-style $res.alias_path)]
        } else {
            [(path-style $res.real)]
        }
        let parts = ($what_parts | append [(plain " <- ") (path-style $blp_rel)])
        report $exists $parts
        if not $exists { $issues = $issues + 1 }
    }

    section "4. Every dynamic class in blp files must be backed by a Python class with matching template resource"
    for blp in $on_disk_blps {
        let blp_abs = ($root | path join $blp)
        let classes = (dynamic-classes $blp_abs)
        let expected_ui = (expected-ui-for-blp $blp)
        for class_name in $classes {
            let known = ($class_name in $class_to_resource)
            if $known {
                let res = ($class_to_resource | get $class_name)
                let py_rel = ($py_classes | where class_name == $class_name | get py_file.0 | path relative-to $root)
                let expected_res = $"($APP_RES_PREFIX_SLASH)($expected_ui)"
                let ok = ($res == $expected_res)
                report $ok [
                    (path-style $blp) (plain " declares dynamic class ") (path-style $class_name) (plain " backed by ") (path-style $py_rel) (plain " -> ") (path-style $res)
                ]
                if not $ok { $issues = $issues + 1 }
            } else {
                report false [
                    (path-style $blp) (plain " declares dynamic class ") (path-style $class_name) (plain ": no matching Python @Gtk.Template class")
                ]
                $issues = $issues + 1
            }
        }
    }

    print --stderr ""
    if $issues == 0 {
        print --stderr $"All checks passed. Scanned ($refs | length) refs, ($on_disk_blps | length) blp files."
        exit 0
    } else {
        print --stderr $"Found ($issues) issue."
        exit 1
    }
}
