import os
import sys

# Ensure local src path is importable
_here = os.path.dirname(os.path.dirname(__file__))  # delta_vision folder
_src = os.path.join(_here, "src")
if os.path.isdir(_src) and _src not in sys.path:
    sys.path.insert(0, _src)
