#!/usr/bin/env nu

def main []: nothing -> nothing {
  # result looks like:
  # [[path, line_numbers]; ["src/app.py", [1, 3, 10]]]
  # where line_numbers is 1-based.
  let finding = search-occurrences
  $finding | each {|r|
    let line_numbers = $r.line_numbers | each {|i| $i - 1 }
    handle-file $r.path $line_numbers }
}

def handle-file [file_path: string, line_numbers: list<int>]: nothing -> nothing {
  let content = open --raw $file_path | lines
  let new_content = $content | enumerate | each {|pair|
    if ($line_numbers | any {|i| $i == $pair.index }) {
      remove-pyright-from-line $pair.item
    } else {
      $pair.item
    }
  } | str join (char newline)
  let new_content = if ($new_content | str ends-with (char newline)) {
    $new_content
  } else {
    $new_content + (char newline)
  }
  $new_content | save -f $file_path
}

def remove-pyright-from-line [line: string]: nothing -> string {
  $line | str replace -r ' +# pyright: ignore\[reportMissingModuleSource\]' '' | str trim -r
}

def search-occurrences []: nothing -> table<path: string, line_numbers: list<int>> {
  let files = ^rg -F '# pyright:' -t py --json
  $files
    | from json --objects
    | where type == 'match'
    | get data
    | select path.text line_number
    | rename path
    | group-by path
    | items {|k, v| {path: $k, line_numbers: ($v | get line_number)} }
}
