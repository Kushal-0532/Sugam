#!/usr/bin/env bash
# M0 check: phone reachable, u2 works, and NOTHING got installed.
set -euo pipefail
cd "$(dirname "$0")/.."
adb devices | grep -w device >/dev/null || { echo "no authorized device (adb devices)"; exit 1; }
echo "model:   $(adb shell getprop ro.product.model)"
echo "android: $(adb shell getprop ro.build.version.release) (SDK $(adb shell getprop ro.build.version.sdk))"
echo "os:      $(adb shell getprop ro.build.display.id)"
adb shell pm list packages | sort > logs/pkgs_before.txt
.venv/bin/python - <<'PY'
import uiautomator2 as u2
d = u2.connect()
print("current:", d.app_current())
d.screenshot("logs/setup_screen.png")
open("logs/setup_hierarchy.xml", "w").write(d.dump_hierarchy())
print("screenshot + hierarchy saved in logs/")
PY
adb shell pm list packages | sort > logs/pkgs_after.txt
if diff logs/pkgs_before.txt logs/pkgs_after.txt; then echo "PACKAGES UNCHANGED: $(wc -l < logs/pkgs_after.txt) packages"; else echo "PACKAGES CHANGED"; exit 2; fi
