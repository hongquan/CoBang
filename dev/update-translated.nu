#!/usr/bin/env nu

let po_folder = $env.CURRENT_FILE | path dirname | path dirname | path join "po"
let template_file = $po_folder | path join "cobang.pot"
# Loop over *.po files
ls ($'($po_folder)/*.po' | into glob) | each { |po_file|
    # Get language code from po file name
    let lang_code = $po_file | get name | path basename | split column "." | first
    # Use msgmerge to update translated strings
    msgmerge -U $"($po_file | get name)" $"($template_file)"
    $"Updated ($po_file | get name) with new strings from cobang.pot"
}
