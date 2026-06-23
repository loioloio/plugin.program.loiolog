# -*- coding: utf-8 -*-
"""loiolog: Advanced Kodi log manager. Entry point."""
import os
import sys

# Guarded so it stays correct under reuselanguageinvoker (this script re-runs per
# invocation while modules stay loaded; an unguarded insert would pile up dupes).
_LIB = os.path.join(os.path.dirname(__file__), 'resources', 'lib')
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from router import handle_runscript, route

if __name__ == "__main__":
    if not handle_runscript():
        route()
