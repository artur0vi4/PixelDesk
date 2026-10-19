"""Helper for run.bat / build_exe.bat (must stay ASCII only).

Usage:
    python pw_check.py interp   -> exit 0 if this interpreter runs at all
    python pw_check.py          -> exit 0 if all required libraries are present
"""
import sys

REQUIRED = ("PySide6", "psutil", "requests")

if len(sys.argv) > 1 and sys.argv[1] == "interp":
    sys.exit(0)

missing = []
for mod in REQUIRED:
    try:
        __import__(mod)
    except Exception as exc:  # ImportError or a broken installation
        missing.append("%s (%s)" % (mod, exc))

if missing:
    print("MISSING LIBRARIES:")
    for m in missing:
        print("  - " + m)
    sys.exit(1)

print("ALL_OK")
sys.exit(0)
