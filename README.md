# Status Light

Daemon and CLI program for a 4×4 NeoPixel LED matrix framed and hanging next to
my PC.

The animations run on the device firmware. The daemon only forwards mode
commands over serial, so once an animation is started the unit keeps running it
on its own — even if the host disconnects.

## Installation

Install as a tool via `uv` (creates `status-light` and `status-light-daemon`
binaries in `~/.local/bin`):

```sh
uv tool install .
```

For local development:

```sh
uv sync
```

Alternatively, Arch packages are available:

```sh
pacman -S platformio-core python-pyserial
```


## Firmware

The firmware implements the animations. Each `start:<name>` command selects a
mode that runs in `loop()` until another command arrives.

### Build

```sh
make build
```

### Upload

```sh
make upload
```

### LSP support

```sh
uv run pio run -t compiledb
```

## Usage

First, start the daemon:

```sh
status-light-daemon --port /dev/ttyUSB0
```

The daemon listens on a Unix socket at `/tmp/status-light.sock` and forwards
commands to the Arduino over serial. All `status-light` commands communicate
through that socket, so the daemon must be running.

On startup (and after a reconnect) the daemon re-applies the last requested
mode, defaulting to `idle`.


## Commands

### `start`

Starts an animation. The animation runs on the firmware until another command
is sent.

```sh
status-light start idle
status-light start notify
```

| Name | Description |
|------|-------------|
| `idle` | Random pixels fade in to random colors, hold, then fade out |
| `notify` | Notification animation (currently a placeholder green pulse) |


### `stop`

Stops the current animation and clears the display.

```sh
status-light stop
```


### `status`

Reports whether the daemon is connected to the LED matrix. Exits `0` when
connected, `1` otherwise. Used by the quickshell component.

```sh
status-light status
```


## Serial protocol

The daemon and firmware speak a tiny newline-terminated protocol over serial:

| Command | Effect |
|---------|--------|
| `start:idle` | Run the idle animation |
| `start:notify` | Run the notification animation |
| `stop` | Stop animating and clear the display |


## Permissions

### Arch Linux

Install the udev rules package:

```sh
pacman -S platformio-core-udev
```

### Manual

Add udev rules for your board to `/etc/udev/rules.d/99-platformio-udev.rules`.
See the [PlatformIO udev rules documentation](https://docs.platformio.org/en/latest/core/installation/udev-rules.html)
for the full rule set.


## License

[MIT](LICENSE)
