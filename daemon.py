#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import signal
import serial
from concurrent.futures import ThreadPoolExecutor

SOCKET_PATH = "/tmp/status-light.sock"
SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200
LED_COUNT = 16

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("status-light")


def apply_brightness(r, g, b, brightness):
    f = max(0.0, min(1.0, brightness))
    return int(r * f), int(g * f), int(b * f)


def expand_pixels(pixels):
    """Expand single-pixel shorthand to full LED_COUNT list."""
    if len(pixels) == 1:
        pixels = pixels * LED_COUNT
    elif len(pixels) < LED_COUNT:
        blank = {"r": 0, "g": 0, "b": 0, "brightness": 0.0}
        pixels = pixels + [blank] * (LED_COUNT - len(pixels))
    return pixels[:LED_COUNT]


class StatusLight:
    def __init__(self, port=SERIAL_PORT, baud=BAUD_RATE):
        self.ser = serial.Serial(port, baud, timeout=1)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self._anim_task = None
        self._loop = None
        log.info(f"Serial connected: {port} @ {baud}")

    def _write(self, data: bytes):
        if self.ser.is_open:
            self.ser.write(data)

    async def _send(self, data: bytes):
        await self._loop.run_in_executor(self.executor, self._write, data)

    async def send_frame(self, pixels):
        pixels = expand_pixels(pixels)
        parts = []
        for p in pixels:
            r, g, b = apply_brightness(p["r"], p["g"], p["b"], p.get("brightness", 1.0))
            parts.append(f"{r:02X}{g:02X}{b:02X}")
        cmd = "F:" + ",".join(parts) + "\n"
        await self._send(cmd.encode())

    async def clear(self):
        await self._send(b"C\n")

    def _cancel_animation(self):
        if self._anim_task and not self._anim_task.done():
            self._anim_task.cancel()

    async def _run_animation(self, frames, fps, loop):
        delay = 1.0 / max(fps, 0.1)
        try:
            while True:
                for frame in frames:
                    await self.send_frame(frame)
                    await asyncio.sleep(delay)
                if not loop:
                    break
        except asyncio.CancelledError:
            pass

    async def handle_command(self, cmd: dict):
        self._cancel_animation()
        ctype = cmd.get("type", "frame")

        if ctype == "frame":
            await self.send_frame(cmd.get("pixels", [{"r": 0, "g": 0, "b": 0}]))

        elif ctype == "animation":
            frames = [expand_pixels(f) for f in cmd.get("frames", [])]
            if not frames:
                return
            fps = cmd.get("fps", 10)
            loop = cmd.get("loop", False)
            self._anim_task = asyncio.create_task(
                self._run_animation(frames, fps, loop)
            )

        elif ctype == "clear":
            await self.clear()

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info("peername") or "client"
        log.info(f"Connection from {addr}")
        try:
            async for line in reader:
                line = line.strip()
                if not line:
                    continue
                try:
                    cmd = json.loads(line)
                    await self.handle_command(cmd)
                    writer.write(b"ok\n")
                    await writer.drain()
                except (json.JSONDecodeError, KeyError) as e:
                    writer.write(f"error: {e}\n".encode())
                    await writer.drain()
        except Exception as e:
            log.warning(f"Client disconnected: {e}")
        finally:
            writer.close()

    async def run(self):
        self._loop = asyncio.get_running_loop()

        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)

        server = await asyncio.start_unix_server(self.handle_client, SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o600)
        log.info(f"Daemon listening on {SOCKET_PATH}")

        def _shutdown():
            log.info("Shutting down")
            server.close()

        self._loop.add_signal_handler(signal.SIGTERM, _shutdown)
        self._loop.add_signal_handler(signal.SIGINT, _shutdown)

        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=SERIAL_PORT)
    parser.add_argument("--baud", type=int, default=BAUD_RATE)
    args = parser.parse_args()

    light = StatusLight(args.port, args.baud)
    asyncio.run(light.run())
