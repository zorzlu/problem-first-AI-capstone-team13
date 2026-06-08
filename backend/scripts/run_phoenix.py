import mimetypes
try:
    mimetypes.init(files=[])
except Exception:
    pass

import runpy
import sys

if __name__ == '__main__':
    # Run the phoenix server main module as __main__
    # This matches the behavior of python -m phoenix.server.main
    runpy.run_module("phoenix.server.main", run_name="__main__")
