#!/usr/bin/env python3
import asyncio
import json
import logging
import fcntl
import termios
import os
import time
import random
import signal
import pyudev
import serial
from concurrent.futures import ThreadPoolExecutor
from status_light.assets import COLORS

SOCKET_PATH = "/tmp/status-light.sock"
# SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_PORT = "/dev/arduino-status-light"
BAUD_RATE = 115200
LED_COUNT = 16

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("status-light")


def apply_brightness(r, g, b, brightness):
    f = max(0.0, min(1.0, brightness))
    return int(r * f), int(g * f), int(b * f)


def expand_pixels(pixels):
    """Expand pixels to full LED_COUNT list, flattening 4x4 grids."""
    # Flatten 2D (4x4) grid into a flat list, remapping for serpentine wiring.
    # Odd rows run right-to-left on the physical strip, so we reverse them when
    # converting from a visual grid to strip indices.
    if pixels and isinstance(pixels[0], list):
        flat = [None] * 16
        for row in range(4):
            for col in range(4):
                strip_idx = (3 - row) * 4 + ((3 - col) if row % 2 == 1 else col)
                flat[strip_idx] = pixels[row][col]
        pixels = flat

    # Normalize None / missing entries to black/off
    blank = {"r": 0, "g": 0, "b": 0, "brightness": 0.0}
    pixels = [p if p is not None else blank for p in pixels]

    if len(pixels) == 1:
        pixels = pixels * LED_COUNT
    elif len(pixels) < LED_COUNT:
        pixels = pixels + [blank] * (LED_COUNT - len(pixels))
    return pixels[:LED_COUNT]


class StatusLight:
    def __init__(self, port=SERIAL_PORT, baud=BAUD_RATE):
        self._port = port
        self._baud = baud
        self.ser: serial.Serial | None = None
        self._connected = False
        self.executor = ThreadPoolExecutor(max_workers=1)
        self._anim_task = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._udev_observer = None
        self._try_connect()

    def _try_connect(self):
        try:
            self.ser = serial.Serial(self._port, self._baud, timeout=1)
            fcntl.ioctl(self.ser.fileno(), termios.TIOCEXCL)
            self._connected = True
            log.info(f"Serial connected: {self._port} @ {self._baud}")
        except serial.SerialException as e:
            self._connected = False
            log.warning(f"Serial not available: {e}")

    async def clear(self):
        await self._send(b"C\n")

    def _write(self, data: bytes):
        if not self._connected or self.ser is None or not self.ser.is_open:
            return
        for attempt in range(3):
            try:
                self.ser.write(data)
                return
            except serial.SerialException as e:
                log.debug(f"Serial write failed (attempt {attempt + 1}): {e}")
                try:
                    self.ser.close()
                except Exception:
                    pass
                time.sleep(0.1)
                try:
                    self.ser.open()
                    log.info("Serial reconnected")
                except serial.SerialException:
                    continue

    async def _send(self, data: bytes):
        assert self._loop is not None
        await self._loop.run_in_executor(self.executor, self._write, data)

    async def send_pixel(self, idx: int, r: int, g: int, b: int, brightness: float):
        brightness_byte = int(max(0.0, min(1.0, brightness)) * 255)
        cmd = f"P:{idx},{r:02X}{g:02X}{b:02X},{brightness_byte}\n"
        await self._send(cmd.encode())

    async def send_frame(self, pixels):
        pixels = expand_pixels(pixels)
        parts = []
        for p in pixels:
            r, g, b = apply_brightness(p["r"], p["g"], p["b"], p.get("brightness", 1.0))
            parts.append(f"{r:02X}{g:02X}{b:02X}")
        cmd = "F:" + ",".join(parts) + "\n"
        await self._send(cmd.encode())

    def _cancel_animation(self):
        if self._anim_task and not self._anim_task.done():
            self._anim_task.cancel()

    def _start_udev_monitor(self):
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by('tty')
        self._udev_observer = pyudev.MonitorObserver(monitor, callback=self._udev_event)
        self._udev_observer.start()
        log.info("udev monitor started")

    def _udev_event(self, device):
        log.info(f"udev event: action={device.action} node={device.device_node}")
        if device.device_node != self._port:
            return
        if device.action == 'remove' and self._connected:
            self._connected = False
            try:
                if self.ser is not None:
                    self.ser.close()
            except Exception:
                pass
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._handle_disconnect)
        elif device.action == 'add' and not self._connected:
            if self._loop is not None:
                asyncio.run_coroutine_threadsafe(self._do_reconnect(), self._loop)

    def _handle_disconnect(self):
        log.warning(f"Device disconnected: {self._port}")
        self._cancel_animation()

    async def _do_reconnect(self):
        log.info(f"Device appeared at {self._port}, reconnecting...")
        assert self._loop is not None
        await self._loop.run_in_executor(self.executor, self._try_connect)
        self._anim_task = asyncio.create_task(self._run_idle_animation())

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

    async def _run_idle_animation(self):
        TICK        = 1 / 15   # 15 FPS
        FADE_STEPS  = 15       # 1 s fade at 15 FPS
        MAX_ACTIVE  = 6
        OFF         = {"r": 0, "g": 0, "b": 0, "brightness": 0.0}
        color_names = list(COLORS.keys())
        states: dict = {}      # idx -> {r,g,b, phase, step, hold_ticks}
        spawn_cooldown = 0

        try:
            while True:
                available = [i for i in range(LED_COUNT) if i not in states]
                if spawn_cooldown <= 0 and available and len(states) < MAX_ACTIVE:
                    idx = random.choice(available)
                    c   = COLORS[random.choice(color_names)]
                    states[idx] = {
                        "r": c["r"], "g": c["g"], "b": c["b"],
                        "phase": "in", "step": 0,
                        "hold_ticks": random.randint(15, 60),  # 1–4 s
                    }
                    spawn_cooldown = random.randint(5, 20)      # 0.3–1.3 s
                spawn_cooldown -= 1

                finished = []
                for idx, s in states.items():
                    if s["phase"] == "in":
                        s["step"] += 1
                        if s["step"] > FADE_STEPS:
                            s["phase"] = "hold"
                            s["step"]  = 0
                    elif s["phase"] == "hold":
                        s["step"] += 1
                        if s["step"] >= s["hold_ticks"]:
                            s["phase"] = "out"
                            s["step"]  = FADE_STEPS
                    elif s["phase"] == "out":
                        s["step"] -= 1
                        if s["step"] < 0:
                            finished.append(idx)
                for idx in finished:
                    del states[idx]

                frame = []
                for i in range(LED_COUNT):
                    if i in states:
                        s = states[i]
                        if s["phase"] == "in":
                            br = s["step"] / FADE_STEPS
                        elif s["phase"] == "hold":
                            br = 1.0
                        else:
                            br = max(0.0, s["step"] / FADE_STEPS)
                        frame.append({"r": s["r"], "g": s["g"], "b": s["b"], "brightness": br})
                    else:
                        frame.append(OFF)

                await self.send_frame(frame)
                await asyncio.sleep(TICK)

        except asyncio.CancelledError:
            raise

    async def handle_command(self, cmd: dict):
        ctype = cmd.get("type", "frame")

        if ctype in ("frame", "clear", "animation", "idle"):
            if self._anim_task and not self._anim_task.done():
                self._anim_task.cancel()
                try:
                    await self._anim_task
                except asyncio.CancelledError:
                    pass

        if ctype == "frame":
            await self.send_frame(cmd.get("pixels", [{"r": 0, "g": 0, "b": 0}]))

        elif ctype == "clear":
            await self.clear()

        elif ctype == "animation":
            frames = [expand_pixels(f) for f in cmd.get("frames", [])]
            if not frames:
                return None
            fps = cmd.get("fps", 10)
            loop = cmd.get("loop", False)
            self._anim_task = asyncio.create_task(
                self._run_animation(frames, fps, loop)
            )

        elif ctype == "idle":
            self._anim_task = asyncio.create_task(self._run_idle_animation())

        elif ctype == "pixel":
            idx = cmd.get("index", 0)
            r = cmd.get("r", 0)
            g = cmd.get("g", 0)
            b = cmd.get("b", 0)
            brightness = cmd.get("brightness", 1.0)
            await self.send_pixel(idx, r, g, b, brightness)

        elif ctype == "status":
            payload = json.dumps({"connected": self._connected, "port": self._port})
            return payload.encode() + b"\n"

        else:
            log.warning(f"Unknown command type: {ctype!r}")

        return None

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
                    ctype = cmd.get("type", "frame")
                    if not self._connected and ctype != "status":
                        writer.write(b"error: device not connected\n")
                        await writer.drain()
                        continue
                    response = await self.handle_command(cmd)
                    writer.write(response if response is not None else b"ok\n")
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
        self._start_udev_monitor()

        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)

        server = await asyncio.start_unix_server(
            self.handle_client,
            SOCKET_PATH,
            limit=256 * 1024  # 256 KB
        )
        os.chmod(SOCKET_PATH, 0o600)
        log.info(f"Daemon listening on {SOCKET_PATH}")

        log.info("Init complete: starting idle animation")
        self._anim_task = asyncio.create_task(self._run_idle_animation())

        def _shutdown():
            log.info("Shutting down, please wait...")
            self._cancel_animation()
            if self._udev_observer:
                self._udev_observer.stop()
                self._udev_observer = None
            server.close()
            if os.path.exists(SOCKET_PATH):
                os.unlink(SOCKET_PATH)

        self._loop.add_signal_handler(signal.SIGTERM, _shutdown)
        self._loop.add_signal_handler(signal.SIGINT, _shutdown)

        try:
            async with server:
                try:
                    await server.serve_forever()
                except asyncio.CancelledError:
                    log.info("Server stopped cleanly")
        finally:
            if self._udev_observer:
                self._udev_observer.stop()
            if self.ser is not None and self.ser.is_open:
                self.ser.close()
                log.info("Serial port closed")
            self.executor.shutdown(wait=False)
            log.info("Shutdown complete")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=SERIAL_PORT)
    parser.add_argument("--baud", type=int, default=BAUD_RATE)
    args = parser.parse_args()

    light = StatusLight(args.port, args.baud)
    asyncio.run(light.run())


if __name__ == "__main__":
    main()
