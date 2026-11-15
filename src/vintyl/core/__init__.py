"""
The cutter core: paths in, cutter commands out. Nothing in this package
imports a GUI toolkit, so it can be tested and used without a window.

Coordinates used everywhere in the core ("material coordinates"):
    millimetres; x runs along the material (the feed direction, unlimited
    on a roll), y runs across it, from 0 to the cutting width; (0, 0) is
    the point set with the cutter's Origin key.

Copyright (C) 2026 Vintyl contributors
Licensed under the GNU General Public License v3 or later. See LICENSE.
"""
