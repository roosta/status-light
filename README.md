Status Light
===

Daemon and CLI program for a 4x4 NeoPixel LED matrix framed and hanging next to
my PC.

## Dependencies

Install dependencies via `uv`

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
uv run daemon.py --port /dev/ttyUSB0

# Example commands
uv run cli.py frame red --brightness 0.5
uv run cli.py frame green
uv run cli.py animation --name pulse-red --loop
uv run cli.py animation --name blink-yellow --fps 4 --loop
uv run cli.py clear
```


```sh
uv run cli.py animation --file my_anim.json --fps 5 --loop
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
