from pprint import pprint

# Predefined colors
COLORS = {
    "red":         {"r": 255, "g": 0,   "b": 0},
    "pink":        {"r": 160, "g": 20,  "b": 30},
    "green":       {"r": 10,  "g": 230, "b": 30},
    "blue":        {"r": 0,   "g": 50,  "b": 255},
    "yellow":      {"r": 220, "g": 200, "b": 0},
    "white":       {"r": 255, "g": 255, "b": 255},
    "purple":      {"r": 180, "g": 0,   "b": 180},
    "orange":      {"r": 255, "g": 80,  "b": 0},
    "cyan":        {"r": 10,  "g": 100, "b": 200},
    "light-green": {"r": 150, "g": 200, "b": 0}
}


# ── pixel helpers ────────────────────────────────────────────────────────────

def px(color_name: str, brightness: float = 1.0) -> dict:
    """Return a pixel dict for a named color."""
    c = COLORS[color_name]
    return {**c, "brightness": brightness}

_ = {"r": 0, "g": 0, "b": 0, "brightness": 0.0}   # off / blank cell

# ── named icons (4x4 grids laid out visually) ─────────────────────────────────

NAMED_ICONS = {
    # ♥ approximated heart
    "heart": [
        _,           px("red"),  px("red"),  _,
        px("red"),   px("red"),  px("red"),  px("red"),
        px("red"),   px("red"),  px("red"),  px("red"),
        _,           px("red"),  px("red"),  _,
    ],
    # + cross
    "cross": [
        _,            px("green"), px("green"), _,
        px("green"),  px("green"), px("green"), px("green"),
        px("green"),  px("green"), px("green"), px("green"),
        _,            px("green"), px("green"), _,
    ],
    # □ hollow border
    "border": [
        px("blue"), px("blue"), px("blue"), px("blue"),
        px("blue"), _,          _,          px("blue"),
        px("blue"), _,          _,          px("blue"),
        px("blue"), px("blue"), px("blue"), px("blue"),
    ],
    # ✕ diagonal X
    "x-mark": [
        px("yellow"), _,            _,            px("yellow"),
        _,            px("yellow"), px("yellow"), _,
        _,            px("yellow"), px("yellow"), _,
        px("yellow"), _,            _,            px("yellow"),
    ],
    # four corners only
    "corners": [
        px("white"), _, _, px("white"),
        _,           _, _, _,
        _,           _, _, _,
        px("white"), _, _, px("white"),
    ],
}

# ── per-cell animation helpers ───────────────────────────────────────────────

def _grid_frame(lit_indices, color):
    """Build a flat 16-pixel frame; lit indices use `color`, rest are off."""
    return [color if i in lit_indices else _ for i in range(16)]

# Physical column -> strip indices (left=0, right=3)
_PHYSICAL_COLS = [
    {12, 11,  4,  3},  # col 0 (left)
    {13, 10,  5,  2},  # col 1
    {14,  9,  6,  1},  # col 2
    {15,  8,  7,  0},  # col 3 (right)
]

# Physical row -> strip indices (top=0, bottom=3)
_PHYSICAL_ROWS = [
    {12, 13, 14, 15},  # row 0 (top)
    { 8,  9, 10, 11},  # row 1
    { 4,  5,  6,  7},  # row 2
    { 0,  1,  2,  3},  # row 3 (bottom)
]

# Clockwise spiral from physical top-left inward
_SPIRAL_ORDER = [12, 13, 14, 15, 8, 7, 0, 1, 2, 3, 4, 11, 10, 9, 6, 5]

# Left-to-right, top-to-bottom fill in physical space
_SNAKE_ORDER  = [12, 13, 14, 15, 11, 10, 9, 8, 4, 5, 6, 7, 3, 2, 1, 0]

NAMED_ANIMATIONS = {
    "notification": lambda fps, loop, color=None: {
        "type": "animation",
        "fps": fps,
        "loop": loop,
        "frames": (
            [
                _grid_frame(_PHYSICAL_COLS[0] | _PHYSICAL_COLS[3], px(color or "cyan")),
                _grid_frame(_PHYSICAL_COLS[1] | _PHYSICAL_COLS[2], px(color or "cyan")),
                _grid_frame({13, 14, 10, 9, 2, 1}, px(color or "cyan")),
            ] +
            [
                _grid_frame({13, 14, 10, 9, 2, 1}, px(color or "cyan", i / 20))
                for i in range(20, -1, -1)
            ]
        ),
    },
    "pulse": lambda fps, loop, color=None: {
        "type": "animation",
        "fps": fps,
        "loop": loop,
        "frames": (
            [[{**COLORS[color or "red"], "brightness": i / 20}] for i in range(21)] +
            [[{**COLORS[color or "red"], "brightness": i / 20}] for i in range(20, -1, -1)]
        ),
    },
    "blink": lambda fps, loop, color=None: {
        "type": "animation",
        "fps": fps,
        "loop": loop,
        "frames": [
            [{**COLORS[color or "red"],  "brightness": 1.0}],
            [{"r": 0, "g": 0, "b": 0,   "brightness": 0.0}],
        ],
    },
    "rainbow": lambda fps, loop, color=None: {
        "type": "animation",
        "fps": fps,
        "loop": loop,
        "frames": [
            [{"r": c["r"], "g": c["g"], "b": c["b"], "brightness": 1.0}]
            for c in [
                COLORS["red"], COLORS["orange"], COLORS["yellow"],
                COLORS["green"], COLORS["cyan"], COLORS["blue"], COLORS["purple"],
            ]
        ],
    },
    # single column sweeps left → right
    "wipe-right": lambda fps, loop, color=None: {
        "type": "animation", "fps": fps, "loop": loop,
        "frames": [
            _grid_frame(_PHYSICAL_COLS[col], px(color or "cyan"))
            for col in range(4)
        ],
    },
    # single column sweeps right → left
    "wipe-left": lambda fps, loop, color=None: {
        "type": "animation", "fps": fps, "loop": loop,
        "frames": [
            _grid_frame(_PHYSICAL_COLS[col], px(color or "cyan"))
            for col in range(3, -1, -1)
        ],
    },
    # single row sweeps top → bottom
    "wipe-down": lambda fps, loop, color=None: {
        "type": "animation", "fps": fps, "loop": loop,
        "frames": [
            _grid_frame(_PHYSICAL_ROWS[row], px(color or "purple"))
            for row in range(4)
        ],
    },
    # single row sweeps bottom → top
    "wipe-up": lambda fps, loop, color=None: {
        "type": "animation", "fps": fps, "loop": loop,
        "frames": [
            _grid_frame(_PHYSICAL_ROWS[row], px(color or "purple"))
            for row in range(3, -1, -1)
        ],
    },
    # alternating checkerboard flash
    # With serpentine wiring, even strip indices always land on physically
    # alternating (checkerboard) positions across all rows.
    "checkerboard": lambda fps, loop, color=None: {
        "type": "animation", "fps": fps, "loop": loop,
        "frames": [
            _grid_frame({i for i in range(16) if i % 2 == 0}, px(color or "white")),
            _grid_frame({i for i in range(16) if i % 2 == 1}, px(color or "white")),
        ],
    },
    # clockwise spiral fill inward
    "spiral": lambda fps, loop, color=None: {
        "type": "animation", "fps": fps, "loop": loop,
        "frames": [
            _grid_frame(set(_SPIRAL_ORDER[:i + 1]), px(color or "cyan"))
            for i in range(16)
        ],
    },
    # snake (boustrophedon) fill
    "snake": lambda fps, loop, color=None: {
        "type": "animation", "fps": fps, "loop": loop,
        "frames": [
            _grid_frame(set(_SNAKE_ORDER[:i + 1]), px(color or "green"))
            for i in range(16)
        ],
    },
}

