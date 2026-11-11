#!/bin/sh
# Run the headless tests on several Blender versions and print one line per version.
#   BLENDERS="/path/a/Blender /path/b/blender" tests/run_matrix.sh [test file]
# Without BLENDERS it uses every Blender.app it finds in /Applications.
cd "$(dirname "$0")/.." || exit 1
TEST="${1:-tests/test_generic.py}"
if [ -z "$BLENDERS" ]; then
    for app in /Applications/Blender*.app; do
        [ -x "$app/Contents/MacOS/Blender" ] && BLENDERS="$BLENDERS $app/Contents/MacOS/Blender"
    done
fi
bad=0
for b in $BLENDERS; do
    ver=$("$b" --version 2>/dev/null | head -1)
    out=$("$b" -b --factory-startup --python "$TEST" 2>&1 | grep -E "^RESULT" | tail -1 | cut -c1-300)
    [ -z "$out" ] && out="RESULT (no result line: the test crashed)"
    echo "$ver: $out"
    case "$out" in "RESULT ALL PASS"*) ;; *) bad=1 ;; esac
done
exit $bad
