Status Light
===

Daemon and CLI program for a 4x4 NeoPixel LED matrix framed and hanging next to
my PC.

## Dependencies

Install as a tool via `uv` (creates `status-light` and `status-light-daemon` binaries in `~/.local/bin`):

```sh
uv tool install .
```

Alternatively, for local development:

```sh
uv sync
```

Alternatively there are also a pacman packages:

```sh
pacman -S platformio-core python-pyserial
```

## Building

```sh
make build
```

Uploading:
```sh
make upload
```

## Usage

```sh
# start the daemon
status-light-daemon --port /dev/ttyUSB0

# Example commands
status-light frame red --brightness 0.5
status-light frame green
status-light animation --name pulse-red --loop
status-light animation --name blink-yellow --fps 4 --loop
status-light clear
```


```sh
status-light animation --file my_anim.json --fps 5 --loop
```

```json
{
  "frames": [
    [{"r": 255, "g": 0, "b": 0, "brightness": 1.0}],
    [{"r": 0, "g": 255, "b": 0, "brightness": 1.0}]
  ]
}
```

## Permissions

### Arch

Install package platformio-core-udev

```sh
pacman -S platformio-core-udev
```

### Manual

- [99-platformio-udev.rules — PlatformIO latest documentation](https://docs.platformio.org/en/latest/core/installation/udev-rules.html)

Added add udev rules for boards here: `/etc/udev/rules.d/99-platformio-udev.rules`

## LSP

```sh
uv run pio run -t compiledb
```

## LICENSE

[MIT](LICENSE)
