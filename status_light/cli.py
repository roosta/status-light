#!/usr/bin/env python3
import argparse
import json
import socket
import sys
from status_light.assets import NAMED_ICONS, NAMED_ANIMATIONS, COLORS

SOCKET_PATH = "/tmp/status-light.sock"

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
    ap.add_argument("--color", choices=COLORS.keys(), default=None,
                    help="Override the animation color (uses per-animation default if omitted)")

    # clear
    sub.add_parser("clear", help="Turn off all LEDs")

    # status
    sub.add_parser("status", help="Check daemon connection to the LED matrix")

    # raw (power-user escape hatch)
    rp = sub.add_parser("raw", help="Send raw JSON command")
    rp.add_argument("json")

    args = parser.parse_args()

    if args.command == "clear":
        cmd = {"type": "clear"}

    elif args.command == "status":
        cmd = {"type": "status"}

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
            cmd = NAMED_ANIMATIONS[args.name](args.fps, args.loop, args.color)
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
        if args.command == "status":
            data = json.loads(response)
            print(f"connected: {str(data['connected']).lower()}  port: {data['port']}")
            sys.exit(0 if data["connected"] else 1)
        if response.startswith("error"):
            print(response, file=sys.stderr)
            sys.exit(1)
        print(response)
    except (ConnectionRefusedError, FileNotFoundError):
        print("error: daemon not running — start with: python daemon.py", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
