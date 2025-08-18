import os
import sys

# Ensure local src package is used when running from the repo
_here = os.path.dirname(__file__)
_src = os.path.join(_here, "src")
if os.path.isdir(_src) and _src not in sys.path:
    sys.path.insert(0, _src)


if __name__ == "__main__":
    from delta_vision.entry_points import main

    main()
