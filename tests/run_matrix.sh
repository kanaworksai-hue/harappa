#!/bin/sh
# Run the headless tests on several Blender versions and print one line per version and test file.
#   BLENDERS="/path/a/Blender /path/b/blender" tests/run_matrix.sh [test file ...]
# Without BLENDERS it uses every Blender.app it finds in /Applications. Without test files it runs
# tests/test_generic.py, tests/test_custom.py and tests/test_blend.py.
cd "$(dirname "$0")/.." || exit 1
TESTS="$*"
[ -z "$TESTS" ] && TESTS="tests/test_generic.py tests/test_custom.py tests/test_blend.py"
if [ -z "$BLENDERS" ]; then
    for app in /Applications/Blender*.app; do
        [ -x "$app/Contents/MacOS/Blender" ] && BLENDERS="$BLENDERS $app/Contents/MacOS/Blender"
    done
fi
bad=0
for b in $BLENDERS; do
    ver=$("$b" --version 2>/dev/null | head -1)
    for t in $TESTS; do
        out=$("$b" -b --factory-startup --python "$t" 2>&1 | grep -E "^RESULT" | tail -1 | cut -c1-300)
        [ -z "$out" ] && out="RESULT (no result line: the test crashed)"
        echo "$ver $(basename "$t"): $out"
        case "$out" in "RESULT ALL PASS"*) ;; *) bad=1 ;; esac
    done
done
exit $bad
