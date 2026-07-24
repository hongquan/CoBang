#!/usr/bin/env nu

# Read the "./generated-sources.yaml" (use `path self` to deduce the file path) file to:
# - Identify the Python packages.
# - Use PyPI API to retrieve the link and hash of the wheel files for:
#   + CPython 3.13 and 3.14.
#   + manylinux_x_y (priority orders: manylinux_2_34, manylinux_2_28, manylinux2014)
#   + x86_64 and aarch64
# For example with Pillow package:
# - type: file
#   url: https://files.pythonhosted.org/packages/20/39/c685d05c06deecfd4e2d1950e9a908aa2ca8bc4e6c3b12d93b9cafbd7837/pillow-12.0.0-cp313-cp313-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl
#   sha256: 0b817e7035ea7f6b942c13aa03bb554fc44fea70838ea21f8eb31c638326584e
# - type: file
#   url: https://files.pythonhosted.org/packages/38/57/755dbd06530a27a5ed74f8cb0a7a44a21722ebf318edbe67ddbd7fb28f88/pillow-12.0.0-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
#   sha256: f4f1231b7dec408e8670264ce63e9c71409d9583dd21d32c163e25213ee2a344
# Always keep the entry for source tarball for fallback.
# If the package does not have platform-dependent wheel file, then find wheel file for "py3-none-any".
# The example is for old version, we should use the version that match the "./generated-sources.yaml".
# Write the result to stdout, or to a file if -o is specified.

use std

# Resolve generated-sources.yaml relative to this script's location
const input_file = (path self | path dirname | path join 'generated-sources.yaml')

def extract-version [url: string] {
  # Extract version from URL filename
  # Examples:
  #   pillow-12.3.0.tar.gz → 12.3.0
  #   typing_extensions-4.16.0-py3-none-any.whl → 4.16.0
  let filename = ($url | path parse | get stem)
  # Strip .tar suffix if present (path parse only strips last extension from .tar.gz)
  let clean = ($filename | str replace -r '\.tar$' '')
  # Use regex: name is non-dash chars, version starts with digit and is non-dash
  $clean | parse -r '(?<name>[^-]+)-(?<version>[0-9][^-]*)' | first | get version
}

def find-wheels [releases: any, version: string] {
  let available = ($releases | get --optional $version | default [])

  # manylinux priority: manylinux_2_34 > manylinux_2_28 > manylinux2014
  let manylinux_tags = ['manylinux_2_34', 'manylinux_2_28', 'manylinux2014']

  # Try platform-specific wheels in manylinux priority order
  for tag in $manylinux_tags {
    let found = ($available | where { |w|
      let f = $w.filename
      let conditions = [
        ($f | str ends-with '.whl'),
        (($f =~ 'cp313') or ($f =~ 'cp314')),
        ($f =~ $tag),
        (($f =~ 'x86_64') or ($f =~ 'aarch64'))
      ]
      $conditions | all { $in }
    })
    if ($found | is-not-empty) {
      return $found
    }
  }

  # Fall back to py3-none-any
  $available | where { |w|
    let conditions = [
      ($w.filename | str ends-with '.whl'),
      ($w.filename =~ 'py3-none-any')
    ]
    $conditions | all { $in }
  }
}

def process-module [module: record] {
  # Extract package name from module name (strip "python3-" prefix)
  let pkg_name = ($module.name | str replace 'python3-' '')

  # Get the current source URL
  let current_source = ($module.sources | first)
  let current_url = $current_source.url
  let version = extract-version $current_url

  # Query PyPI API
  let pypi_url = $"https://pypi.org/pypi/($pkg_name)/json"
  std log info $"Fetching ($pypi_url)..."
  let pypi_data = http get $pypi_url

  let wheels = find-wheels $pypi_data.releases $version

  let new_sources = if ($wheels | is-empty) {
    std log info $"  No matching wheels for ($pkg_name) ($version) - keeping original"
    [$current_source]
  } else {
    let wheel_entries = ($wheels | each { |w|
      {
        type: "file"
        url: $w.url
        sha256: $w.digests.sha256
      }
    })
    # Deduplicate: skip wheels whose URLs are already in original sources
    let existing_urls = ($module.sources | each { |s| $s.url })
    let new_wheel_entries = ($wheel_entries | where { |e| ($e.url not-in $existing_urls) })
    let wheel_count = ($new_wheel_entries | length)
    std log info $"  Found ($wheel_count) new wheels for ($pkg_name) ($version)"
    ([$current_source] | append $new_wheel_entries)
  }

  $module | merge { sources: $new_sources }
}

def main [-o: string] {
  if not ($input_file | path exists) {
    std log error $"Error: ($input_file) not found"
    return 1
  }

  let sources = open $input_file

  let updated_modules = ($sources.modules | each { |module| process-module $module })

  let updated_sources = ($sources | merge { modules: $updated_modules })

  if ($o | is-not-empty) {
    $updated_sources | to yaml | save --force $o
  } else {
    $updated_sources | to yaml
  }
}
