# =============================================================================
# URTC-VISION-TOOL - vision_companion package: __main__.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0 - see LICENSE
# =============================================================================
"""``python -m vision_companion ...`` runs the same command line as the
installed ``vision-companion`` script."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
