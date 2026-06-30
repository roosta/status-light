#!/usr/bin/env python3
import argparse
import json
import socket
import sys

SOCKET_PATH = "/tmp/status-light.sock"

ANIMATIONS = ("idle", "notify", "test")


def send_command(cmd: dict) -> str:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(SOCKET_PATH)
        s.sendall((json.dumps(cmd) + "\n").encode())
        return s.recv(256).decode().strip()


def main():
    parser = argparse.ArgumentParser(prog="status-light", description="Control the LED matrix")
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("start", help="Start an animation")
    sp.add_argument("animation", choices=ANIMATIONS, help="Animation to run")

    sub.add_parser("stop", help="Stop the animation and clear the display")
    sub.add_parser("status", help="Check daemon connection to the LED matrix")

    args = parser.parse_args()

    if args.command == "start":
        cmd = {"type": "start", "name": args.animation}
    else:
        cmd = {"type": args.command}

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
        print("error: daemon not running — start with: status-light-daemon", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
