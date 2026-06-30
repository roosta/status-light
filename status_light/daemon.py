#!/usr/bin/env python3
import asyncio
import json
import logging
import fcntl
import termios
import os
import signal
import pyudev
import serial
from concurrent.futures import ThreadPoolExecutor

SOCKET_PATH = "/tmp/status-light.sock"
SERIAL_PORT = "/dev/arduino-status-light"
BAUD_RATE = 115200

# Animations run on the device firmware; the daemon only forwards mode commands.
ANIMATIONS = ("idle", "notify", "test")
DEFAULT_MODE = "idle"

# Time to let the board finish its bootloader reset before we send a command.
RESET_SETTLE = 2.0

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("status-light")


class StatusLight:
    def __init__(self, port=SERIAL_PORT, baud=BAUD_RATE):
        self._port = port
        self._baud = baud
        self.ser: serial.Serial | None = None
        self._connected = False
        self.executor = ThreadPoolExecutor(max_workers=1)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._udev_observer = None
        self._mode = DEFAULT_MODE   # last requested mode, re-sent on reconnect
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

    def _write(self, data: bytes):
        if not self._connected or self.ser is None or not self.ser.is_open:
            return
        try:
            self.ser.write(data)
        except serial.SerialException as e:
            log.warning(f"Serial write failed (disconnected): {e}")
            self._connected = False
            try:
                self.ser.close()
            except Exception:
                pass

    async def _send(self, data: bytes):
        assert self._loop is not None
        await self._loop.run_in_executor(self.executor, self._write, data)

    async def set_mode(self, mode: str):
        """Remember and forward the requested animation mode to the firmware."""
        self._mode = mode
        await self._send(f"start:{mode}\n".encode())

    async def stop(self):
        self._mode = "stop"
        await self._send(b"stop\n")

    # ── device hotplug ────────────────────────────────────────────────────────

    def _start_udev_monitor(self):
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by('tty')
        self._udev_observer = pyudev.MonitorObserver(monitor, callback=self._udev_event)
        self._udev_observer.start()
        log.info("udev monitor started")

    def _udev_event(self, device):
        log.info(f"udev event: action={device.action} node={device.device_node}")
        if device.device_node != self._port and self._port not in device.device_links:
            return
        if device.action == 'remove' and self._connected:
            self._connected = False
            try:
                if self.ser is not None:
                    self.ser.close()
            except Exception:
                pass
            log.warning(f"Device disconnected: {self._port}")
        elif device.action == 'add' and not self._connected:
            if self._loop is not None:
                asyncio.run_coroutine_threadsafe(self._do_reconnect(), self._loop)

    async def _do_reconnect(self):
        log.info(f"Device appeared at {self._port}, reconnecting...")
        assert self._loop is not None
        await self._loop.run_in_executor(self.executor, self._try_connect)
        if self._connected:
            await asyncio.sleep(RESET_SETTLE)
            await self._restore_mode()

    async def _restore_mode(self):
        """Re-apply the last requested mode (the board resets on connect)."""
        if self._mode == "stop":
            await self.stop()
        else:
            await self.set_mode(self._mode)

    # ── command handling ───────────────────────────────────────────────────────

    async def handle_command(self, cmd: dict):
        ctype = cmd.get("type")

        if ctype == "start":
            name = cmd.get("name")
            if name not in ANIMATIONS:
                return f"error: unknown animation {name!r}\n".encode()
            await self.set_mode(name)

        elif ctype == "stop":
            await self.stop()

        elif ctype == "status":
            payload = json.dumps({"connected": self._connected, "port": self._port})
            return payload.encode() + b"\n"

        else:
            log.warning(f"Unknown command type: {ctype!r}")
            return f"error: unknown command {ctype!r}\n".encode()

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
                    ctype = cmd.get("type")
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

        server = await asyncio.start_unix_server(self.handle_client, SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o600)
        log.info(f"Daemon listening on {SOCKET_PATH}")

        if self._connected:
            log.info("Init complete: starting idle animation")
            await asyncio.sleep(RESET_SETTLE)
            await self._restore_mode()

        def _shutdown():
            log.info("Shutting down, please wait...")
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
