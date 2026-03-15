#!/usr/bin/env python3
import argparse
import json
import socket
import sys

SOCKET_PATH = "/tmp/status-light.sock"

COLORS = {
    "red":    {"r": 255, "g": 0,   "b": 0},
    "pink":   {"r": 160, "g": 20,  "b": 30},
    "green":  {"r": 0,   "g": 255, "b": 0},
    "blue":   {"r": 0,   "g": 0,   "b": 255},
    "yellow": {"r": 255, "g": 200, "b": 0},
    "white":  {"r": 255, "g": 255, "b": 255},
    "purple": {"r": 180, "g": 0,   "b": 180},
    "orange": {"r": 255, "g": 80,  "b": 0},
    "cyan":   {"r": 0,   "g": 220, "b": 220},
}

NAMED_ANIMATIONS = {
    "pulse-red": lambda fps, loop: {
        "type": "animation",
        "fps": fps,
        "loop": loop,
        "frames": (
            [[{"r": 255, "g": 0, "b": 0, "brightness": i / 20}] for i in range(21)] +
            [[{"r": 255, "g": 0, "b": 0, "brightness": i / 20}] for i in range(20, -1, -1)]
        ),
    },
    "blink-red": lambda fps, loop: {
        "type": "animation",
        "fps": fps,
        "loop": loop,
        "frames": [
            [{"r": 255, "g": 0, "b": 0, "brightness": 1.0}],
            [{"r": 0,   "g": 0, "b": 0, "brightness": 0.0}],
        ],
    },
    "blink-yellow": lambda fps, loop: {
        "type": "animation",
        "fps": fps,
        "loop": loop,
        "frames": [
            [{"r": 255, "g": 200, "b": 0, "brightness": 1.0}],
            [{"r": 0,   "g": 0,   "b": 0, "brightness": 0.0}],
        ],
    },
    "rainbow": lambda fps, loop: {
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


def send_command(cmd: dict) -> str:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(SOCKET_PATH)
        s.sendall((json.dumps(cmd) + "\n").encode())
        return s.recv(256).decode().strip()


def main():
    parser = argparse.ArgumentParser(prog="status-light", description="Control the LED matrix")
    sub = parser.add_subparsers(dest="command", required=True)

    # frame
    fp = sub.add_parser("frame", help="Set a static frame / icon")
    fp_src = fp.add_mutually_exclusive_group(required=True)
    fp_src.add_argument("color", nargs="?", choices=COLORS.keys(),
                        help="Solid color across all pixels")
    fp_src.add_argument("--name", choices=NAMED_ICONS.keys(),
                        help="Named icon")
    fp_src.add_argument("--file", metavar="FILE",
                        help="Path to JSON icon file ({\"pixels\": [...]})") 
    fp.add_argument("--brightness", type=float, default=1.0, metavar="0.0-1.0",
                    help="Brightness override for solid-color mode")

    # animation
    ap = sub.add_parser("animation", help="Play an animation")
    ap_src = ap.add_mutually_exclusive_group(required=True)
    ap_src.add_argument("--name", choices=NAMED_ANIMATIONS.keys())
    ap_src.add_argument("--file", metavar="FILE", help="Path to JSON animation file")
    ap.add_argument("--fps", type=float, default=8)
    ap.add_argument("--loop", action="store_true")

    # clear
    sub.add_parser("clear", help="Turn off all LEDs")

    # raw (power-user escape hatch)
    rp = sub.add_parser("raw", help="Send raw JSON command")
    rp.add_argument("json")

    args = parser.parse_args()

    if args.command == "clear":
        cmd = {"type": "clear"}

    elif args.command == "frame":
        if args.name:
            cmd = {"type": "frame", "pixels": NAMED_ICONS[args.name]}
        elif args.file:
            with open(args.file) as f:
                data = json.load(f)
            cmd = {"type": "frame", "pixels": data["pixels"]}
        else:
            c = COLORS[args.color]
            cmd = {"type": "frame", "pixels": [{**c, "brightness": args.brightness}]}

    elif args.command == "animation":
        if args.name:
            cmd = NAMED_ANIMATIONS[args.name](args.fps, args.loop)
        else:
            with open(args.file) as f:
                data = json.load(f)
            cmd = {
                "type": "animation",
                "frames": data["frames"],
                "fps": args.fps,
                "loop": args.loop,
            }

    elif args.command == "raw":
        cmd = json.loads(args.json)

    try:
        response = send_command(cmd)
        if response.startswith("error"):
            print(response, file=sys.stderr)
            sys.exit(1)
        print(response)
    except (ConnectionRefusedError, FileNotFoundError):
        print("error: daemon not running — start with: python daemon.py", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
