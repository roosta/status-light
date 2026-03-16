# Status Light

Daemon and CLI program for a 4×4 NeoPixel LED matrix framed and hanging next to
my PC.

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


## Commands

### `clear`

Turns off all LEDs.

```sh
status-light clear
```


### `frame`

Sets a static image on the matrix. Three ways to specify it:

#### Solid color

Fills every pixel with one color. `--brightness` scales from `0.0` (off) to
`1.0` (full, default).

```sh
status-light frame red
status-light frame green --brightness 0.5
status-light frame blue --brightness 0.25
```

Available colors: `red` `green` `blue` `yellow` `white` `purple` `orange` `cyan`

#### Named icon

Displays a built-in per-cell icon:

```sh
status-light frame --name heart
status-light frame --name border
status-light frame --name cross
status-light frame --name x-mark
status-light frame --name corners
```

| Name | Description |
| `heart` | Red heart shape |
| `cross` | Green plus / cross |
| `border` | Blue hollow border ring |
| `x-mark` | Yellow diagonal X |
| `corners` | White corner dots only |

#### Icon file

Loads a custom icon from a JSON file (see [Icon files](#icon-files) below).

```sh
status-light frame --file my_icon.json
```


### `pixel`

Sets a single pixel by index, color, and brightness. The matrix is numbered
0–15 (see [the grid layout](#json-file-formats) below).

```sh
status-light pixel <index> <color> [--brightness 0.0-1.0]
```

Examples:

```sh
status-light pixel 0 red
status-light pixel 7 blue --brightness 0.5
status-light pixel 15 orange --brightness 0.25
```

Available colors: `red` `green` `blue` `yellow` `white` `purple` `orange` `cyan`


### `animation`

Plays an animation. Use `--loop` to repeat indefinitely and `--fps` to control
speed.

#### Named animation

```sh
status-light animation --name pulse --loop
status-light animation --name blink --fps 4 --loop
status-light animation --name spiral --fps 14 --loop
status-light animation --name wipe-right --fps 4 --loop
status-light animation --name rainbow --fps 6 --loop
```

All named animations accept `--color` to override the default color:

```sh
status-light animation --name pulse   --color blue   --loop
status-light animation --name blink   --color green  --fps 4 --loop
status-light animation --name spiral  --color orange --fps 14 --loop
status-light animation --name wipe-right --color red --fps 4 --loop

```

| Name | Default color | Description |
|------|---------------|-------------|
| `pulse` | red | Smooth brightness fade in and out |
| `blink` | red | Hard on/off flash |
| `rainbow` | — | Cycles through all colors (color override has no effect) |
| `wipe-right` | cyan | Single column sweeps left → right |
| `wipe-left` | cyan | Single column sweeps right → left |
| `wipe-down` | purple | Single row sweeps top → bottom |
| `wipe-up` | purple | Single row sweeps bottom → top |
| `checkerboard` | white | Alternating checker pattern flashes |
| `spiral` | cyan | Fills cells clockwise inward |
| `snake` | green | Fills cells in a boustrophedon (row-alternating) path |

#### Animation file

Loads a custom animation from a JSON file (see [Animation files](#animation-files)
below). `--fps` and `--loop` still apply.

```sh
status-light animation --file my_anim.json --fps 8 --loop
```


## JSON file formats

The matrix is a 4×4 grid of 16 LEDs numbered left-to-right, top-to-bottom:

```
12 13 14 15   ← physical top
11 10  9  8
 4  5  6  7
 3  2  1  0   ← physical bottom (Arduino at index 0, bottom-right)
```

The strip starts at the physical bottom-right corner and snakes upward. This is
handled automatically; visual 4×4 grids in JSON files map to the correct physical
position regardless.

Every pixel is an object with four fields:

```json
{ "r": 255, "g": 0, "b": 0, "brightness": 1.0 }
```

`brightness` scales the RGB values and ranges from `0.0` (off) to `1.0` (full).
Use `null` as shorthand for a pixel that is fully off.


### Icon files

Used with `status-light frame --file <path>`.

The file must have a `pixels` key containing either:

- A **flat list** of exactly 16 pixel objects, or
- A **4×4 nested array** (4 rows of 4 pixels each — mirrors the physical layout).

Flat list example:

```json
{
  "pixels": [
    { "r": 255, "g": 0, "b": 0, "brightness": 1.0 },
    null,
    null,
    { "r": 255, "g": 0, "b": 0, "brightness": 1.0 },
    null,
    { "r": 255, "g": 0, "b": 0, "brightness": 1.0 },
    { "r": 255, "g": 0, "b": 0, "brightness": 1.0 },
    null,
    null,
    { "r": 255, "g": 0, "b": 0, "brightness": 1.0 },
    { "r": 255, "g": 0, "b": 0, "brightness": 1.0 },
    null,
    { "r": 255, "g": 0, "b": 0, "brightness": 1.0 },
    null,
    null,
    { "r": 255, "g": 0, "b": 0, "brightness": 1.0 }
  ]
}
```

4×4 nested array example (the same X pattern, easier to visualise):

```json
{
  "pixels": [
    [ { "r": 255, "g": 200, "b": 0, "brightness": 1.0 }, null, null, { "r": 255, "g": 200, "b": 0, "brightness": 1.0 } ],
    [ null, { "r": 255, "g": 200, "b": 0, "brightness": 1.0 }, { "r": 255, "g": 200, "b": 0, "brightness": 1.0 }, null ],
    [ null, { "r": 255, "g": 200, "b": 0, "brightness": 1.0 }, { "r": 255, "g": 200, "b": 0, "brightness": 1.0 }, null ],
    [ { "r": 255, "g": 200, "b": 0, "brightness": 1.0 }, null, null, { "r": 255, "g": 200, "b": 0, "brightness": 1.0 } ]
  ]
}
```


### Animation files

Used with `status-light animation --file <path>`.

The file must have a `frames` key containing a list of frames. Each frame
follows the same pixel format as an icon file — either a flat list of 16 pixels
or a 4×4 nested array.

Simple two-frame blink:

```json
{
  "frames": [
    [ { "r": 0, "g": 255, "b": 0, "brightness": 1.0 } ],
    [ null ]
  ]
}
```

> A frame with a single pixel is automatically broadcast to all 16 LEDs.

Multi-frame animation with per-cell addressing (arrow pointing right):

```json
{
  "frames": [
    [
      [ null, null, null, null ],
      [ null, { "r": 0, "g": 180, "b": 255, "brightness": 1.0 }, null, null ],
      [ null, null, null, null ],
      [ null, null, null, null ]
    ],
    [
      [ null, null, null, null ],
      [ null, null, { "r": 0, "g": 180, "b": 255, "brightness": 1.0 }, null ],
      [ null, null, null, null ],
      [ null, null, null, null ]
    ],
    [
      [ null, null, { "r": 0, "g": 180, "b": 255, "brightness": 0.5 }, null ],
      [ null, null, null, { "r": 0, "g": 180, "b": 255, "brightness": 1.0 } ],
      [ null, null, { "r": 0, "g": 180, "b": 255, "brightness": 0.5 }, null ],
      [ null, null, null, null ]
    ]
  ]
}
```

```sh
status-light animation --file arrow.json --fps 6 --loop
```


### `raw`

Send a raw JSON command directly to the daemon. Useful for scripting or
debugging.

```sh
status-light raw '{"type": "clear"}'
status-light raw '{"type": "frame", "pixels": [{"r": 255, "g": 0, "b": 0, "brightness": 0.5}]}'
status-light raw '{"type": "pixel", "index": 3, "r": 255, "g": 136, "b": 0, "brightness": 0.5}'
```


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
