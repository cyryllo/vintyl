"""
The packaged program's start (PyInstaller): the same as python -m vintyl.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
import sys

from vintyl.gui.app import main

sys.exit(main())
