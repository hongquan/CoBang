---
name: cobang-release
description: "Use when preparing a new CoBang release: reading current version from meson.build, choosing the next version, inferring changes from Git history, and adding a release entry in the AppStream metainfo file."
---

# cobang-release — Guide for making a CoBang release

## When to use

Whenever the user wants to cut a new release for CoBang.
This includes:
- Preparing release metadata before tagging.
- Adding a `<release>` entry to `data/vn.hoabinh.quan.CoBang.metainfo.xml.in`.
- Verifying the version in `meson.build` matches the upcoming release.

## Workflow

### 1. Read current version from `meson.build`

Open `meson.build` and find the `version:` key in the `project()` call.

Example: `meson.build`

```meson
project(
  'cobang',
  version: '2.5.2',
  ...
)
```

Treat this value as the **current released version**.

### 2. Ask the user what version we are about to make

Ask explicitly for the next version string, for example: `2.6.0` or `2.5.3`.
Use the question tool to avoid assumptions.

### 3. Determine the Git revision range for the changelog

Use the current version as the starting tag.
CoBang tags are prefixed with `v`, so the range is:

```bash
git log v<CURRENT_VERSION>..HEAD --oneline --decorate
```

Example:

```bash
git log v2.5.2..HEAD --oneline --decorate
```

### 4. Infer changes from the commit history

Read every commit message in the range. Group and summarize them into a few user-facing bullet points for AppStream.

Guidelines:
- Use plain English in the style of existing `<release>` entries.
- Keep bullets short (one sentence each, `<p>...</p>`).
- Merge related commits: if several commits all refine one feature, describe the feature once.
- Mention user-visible behavior only; omit internal refactor chores unless they affect behavior.
- If many commits exist after the last tag, focus on the most meaningful 3–6 changes.

Example from `v2.0.0`:

```xml
<release version="2.0.0" date="YYYY-MM-DD" urgency="medium">
  <description translate="no">
    <p>Add QR code generator.</p>
    <p>Add Croatian language.</p>
  </description>
</release>
```

### 5. Pick a release date

Use today's date in `YYYY-MM-DD` format.

### 6. Add the `<release>` entry in the metainfo template

Open `data/vn.hoabinh.quan.CoBang.metainfo.xml.in`.

Insert the new `<release>` block as the **first child** of the `<releases>` element, above existing `<release>` entries.

Format:

```xml
  <releases>
    <release version="NEW_VERSION" date="YYYY-MM-DD" urgency="medium">
      <description translate="no">
        <p>Summary of change 1.</p>
        <p>Summary of change 2.</p>
      </description>
    </release>
    <!-- existing releases follow -->
  </releases>
```

Use `urgency="medium"` unless there is a compelling reason to use `high` or `low`.

### 7. Verify with `appstreamcli`

Run:

```bash
appstreamcli validate --no-net --explain data/vn.hoabinh.quan.CoBang.metainfo.xml.in
```

If validation fails, fix the XML and rerun.

### 8. Optional: validate the whole meson data test target

If the build directory exists:

```bash
meson test -C builddir --suite data
```

This runs the AppStream validation test defined in `data/meson.build`.

## Example: release after v2.5.2

Given commits since `v2.5.2`:

```text
331ccdc Fix invalid property in Blueprint file
0298822 Switch build docs to just commands and refine QR preview pane layout
4b1332f Polish QR preview pane controls and add empty-state placeholder
3b68047 Let users pick a saved Wi-Fi network for QR generation
fe27fde Rename properties
13cc7e8 Replace generator page with redesigned form/preview layout
a2fb714 Rename Generator to OldGenerator to prepare for new design of Generator
32800a3 Add gtk-signal-result skill for GTK child-to-parent communication
c46cea6 Simplify ruff pre-commit hooks
2de54d1 Resolve type-checker errors with walrus operator and type narrowing
27bd0b2 Reorganize Blueprint files
acb555b Reformat Python code
```

If the user chooses `2.6.0`, the resulting entry could be:

```xml
    <release version="2.6.0" date="2026-07-21" urgency="medium">
      <description translate="no">
        <p>Redesign QR code generator with live preview and empty-state placeholder.</p>
        <p>Let users generate QR codes from saved Wi-Fi networks.</p>
        <p>Polish generator controls and preview pane layout.</p>
      </description>
    </release>
```

## What NOT to do

- Do not bump `meson.build` `version:` to the new value yet. Only update the metainfo release list at this stage.
- Do not commit or push changes unless the user explicitly asks for it.
- Do not add release notes for commits that are purely internal (lint, reformat, renaming private symbols, build docs).

## Notes

- The file path is `data/vn.hoabinh.quan.CoBang.metainfo.xml.in`, not the generated `.metainfo.xml`.
- Existing entries use `description translate="no"`; preserve that attribute.
- The release text uses `<p>` paragraphs only; do not use Markdown or lists.
