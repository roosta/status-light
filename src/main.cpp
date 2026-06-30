#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

#define LED_PIN   6
#define LED_COUNT 16
#define BAUD_RATE 115200

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

// ─────────────────────────────────────────────────────────────────────────────
// Animation logic lives on the device. The daemon only sends mode commands over
// serial, so the animation keeps running on its own as long as the unit has
// power — even if the host disconnects.
//
// Serial protocol (newline-terminated):
//   start:idle      run the idle animation
//   start:notify    run the notification animation
//   stop            stop animating and clear the display
// ─────────────────────────────────────────────────────────────────────────────

struct Color { uint8_t r, g, b; };

enum Mode { MODE_STOP, MODE_IDLE, MODE_NOTIFY };
Mode mode = MODE_IDLE;          // default so a bare power-up shows the idle anim

unsigned long lastTick = 0;

const Color PALETTE[] = {
  {255,   0,   0},  // red
  {160,  20,  30},  // pink
  { 10, 230,  30},  // green
  {  0,  50, 255},  // blue
  {220, 200,   0},  // yellow
  {255, 255, 255},  // white
  {180,   0, 180},  // purple
  {255,  80,   0},  // orange
  { 10, 100, 200},  // cyan
  {150, 200,   0},  // light-green
};

// ─────────────────────────────────────────────────────────────────────────────
// Grid coordinate mapping
//
// Physical layout is a 4×4 panel, serpentine wiring: the data line starts at the
// bottom-right, the bottom row runs right→left, then snakes upward alternating
// direction each row, ending at the top-right.
//
// Coordinate convention: (x, y) with x=0 at the LEFT, y=0 at the TOP.
//
//        x=0  x=1  x=2  x=3
//  y=0    12   13   14   15      (top row,    L→R, ends top-right)
//  y=1    11   10    9    8
//  y=2     4    5    6    7
//  y=3     3    2    1    0      (bottom row, R→L, starts bottom-right)
//
// Use gridIndex(x, y) to address pixels by coordinate, and gridXY(i, x, y) to
// go the other way. All other animations should use these so they never have to
// know about the serpentine wiring.
// ─────────────────────────────────────────────────────────────────────────────

const uint8_t GRID_W = 4;
const uint8_t GRID_H = 4;

// Physical (x, y) → strip index.  x: 0=left, y: 0=top.
uint8_t gridIndex(uint8_t x, uint8_t y) {
  uint8_t row = (GRID_H - 1) - y;            // row 0 = bottom (y=3) … row 3 = top
  // Bottom row (row 0) runs right→left; the snake alternates each row up.
  uint8_t pos = (row & 1) ? x : (GRID_W - 1 - x);
  return row * GRID_W + pos;
}

// Strip index → physical (x, y).  Inverse of gridIndex().
void gridXY(uint8_t i, uint8_t &x, uint8_t &y) {
  uint8_t row = i / GRID_W;
  uint8_t pos = i % GRID_W;
  y = (GRID_H - 1) - row;
  x = (row & 1) ? pos : (GRID_W - 1 - pos);
}

// Convenience: set a pixel by coordinate.
inline void gridSet(uint8_t x, uint8_t y, uint32_t color) {
  strip.setPixelColor(gridIndex(x, y), color);
}

// Sanity check: every index must round-trip through xy→index and back.
// Call once in setup() during bring-up; remove afterwards.
void gridSelfTest() {
  for (uint8_t i = 0; i < LED_COUNT; i++) {
    uint8_t x, y;
    gridXY(i, x, y);
    if (gridIndex(x, y) != i) {
      Serial.print(F("Grid map FAIL at index "));
      Serial.println(i);
    }
  }
  Serial.println(F("Grid map self-test complete."));
}

// ── Idle animation ───────────────────────────────────────────────────────────
// Random pixels fade in to a random palette color, hold, then fade out.

const uint8_t PALETTE_SIZE = sizeof(PALETTE) / sizeof(PALETTE[0]);

const uint8_t  IDLE_FADE_STEPS = 15;
const uint8_t  IDLE_MAX_ACTIVE = 6;
const uint16_t IDLE_TICK_MS    = 1000 / 15;   // ~66 ms == 15 FPS

enum Phase { PHASE_OFF, PHASE_IN, PHASE_HOLD, PHASE_OUT };
struct IdleCell {
  Phase   phase;
  uint8_t step;
  uint8_t holdTicks;
  Color   color;
};
IdleCell idleCells[LED_COUNT];
int8_t   idleSpawnCooldown = 0;

void resetIdle() {
  for (uint8_t i = 0; i < LED_COUNT; i++) idleCells[i].phase = PHASE_OFF;
  idleSpawnCooldown = 0;
  strip.clear();
  strip.show();
}

void tickIdle() {
  // Spawn a new cell on a free pixel, respecting the cooldown and active cap.
  if (idleSpawnCooldown <= 0) {
    int8_t  freeCells[LED_COUNT];
    uint8_t freeCount = 0;
    uint8_t active    = 0;
    for (uint8_t i = 0; i < LED_COUNT; i++) {
      if (idleCells[i].phase != PHASE_OFF) active++;
      else freeCells[freeCount++] = i;
    }
    if (freeCount > 0 && active < IDLE_MAX_ACTIVE) {
      uint8_t idx = freeCells[random(freeCount)];
      idleCells[idx].color     = PALETTE[random(PALETTE_SIZE)];
      idleCells[idx].phase     = PHASE_IN;
      idleCells[idx].step      = 0;
      idleCells[idx].holdTicks = random(15, 61);   // 1–4 s at 15 FPS
      idleSpawnCooldown        = random(5, 21);    // 0.3–1.3 s
    }
  }
  idleSpawnCooldown--;

  // Advance phases.
  for (uint8_t i = 0; i < LED_COUNT; i++) {
    IdleCell &c = idleCells[i];
    if (c.phase == PHASE_IN) {
      c.step++;
      if (c.step > IDLE_FADE_STEPS) { c.phase = PHASE_HOLD; c.step = 0; }
    } else if (c.phase == PHASE_HOLD) {
      c.step++;
      if (c.step >= c.holdTicks) { c.phase = PHASE_OUT; c.step = IDLE_FADE_STEPS; }
    } else if (c.phase == PHASE_OUT) {
      if (c.step == 0) c.phase = PHASE_OFF;
      else c.step--;
    }
  }

  // Render.
  for (uint8_t i = 0; i < LED_COUNT; i++) {
    IdleCell &c = idleCells[i];
    float br = 0.0f;
    if (c.phase == PHASE_IN || c.phase == PHASE_OUT) br = (float)c.step / IDLE_FADE_STEPS;
    else if (c.phase == PHASE_HOLD)                  br = 1.0f;
    strip.setPixelColor(i, strip.Color(c.color.r * br, c.color.g * br, c.color.b * br));
  }
  strip.show();
}

// ── Notify animation ─────────────────────────────────────────────────────────
// Center-out pulse: the inner 2×2 grows brighter first; after a short delay the
// outer ring grows too until the whole panel is lit; both hold briefly; the
// outer ring fades out first; the inner square fades out last. Inner and outer
// each pick a random PALETTE color at the start of every cycle.
//
// Timeline (seconds), all derived from these constants:
const float NOTIFY_INNER_IN   = 1.45f;  // inner fade-in
const float NOTIFY_OUTER_DELAY= 0.85f;  // outer start delay
const float NOTIFY_OUTER_IN   = 1.50f;  // outer fade-in
const float NOTIFY_HOLD        = 0.70f;  // hold at full
const float NOTIFY_OUTER_OUT  = 1.25f;  // outer fade-out
const float NOTIFY_INNER_OUT  = 1.80f;  // inner fade-out
const float NOTIFY_GAP         = 1.15f;  // gap before repeat

const uint16_t NOTIFY_TICK_MS = 1000 / 60;   // ~60 FPS for smooth fades

// Inner 2×2 are the center cells: x in {1,2}, y in {1,2}.
bool notifyIsInner(uint8_t i) {
  uint8_t x, y;
  gridXY(i, x, y);
  return (x == 1 || x == 2) && (y == 1 || y == 2);
}

unsigned long notifyStartMs = 0;
Color notifyInnerColor;
Color notifyOuterColor;

// Derived timeline points (computed once in resetNotify).
float notifyFullAt, notifyOutStart, notifyOuterOutEnd, notifyInnerOutEnd, notifyCycle;

// Gamma table for perceptually smooth fades.
uint8_t notifyGamma(float v) {                 // v is 0..1 linear-perceived
  if (v <= 0.0f) return 0;
  if (v >= 1.0f) return 255;
  return (uint8_t)(powf(v, 2.2f) * 255.0f + 0.5f);
}

// Smoothstep easing: 0→1 with eased ends.
float notifySmooth(float t) {
  if (t <= 0.0f) return 0.0f;
  if (t >= 1.0f) return 1.0f;
  return t * t * (3.0f - 2.0f * t);
}

// Brightness 0..1 for a layer given its in/out start times and durations.
float notifyEnvelope(float t, float inStart, float inDur,
                              float outStart, float outDur) {
  if (t < inStart) return 0.0f;
  if (t < inStart + inDur) return notifySmooth((t - inStart) / inDur);
  if (t < outStart) return 1.0f;
  if (t < outStart + outDur) return 1.0f - notifySmooth((t - outStart) / outDur);
  return 0.0f;
}

void notifyPickColors() {
  notifyInnerColor = PALETTE[random(PALETTE_SIZE)];
  // Ensure the outer color differs from the inner one.
  uint8_t outIdx;
  do {
    outIdx = random(PALETTE_SIZE);
  } while (PALETTE[outIdx].r == notifyInnerColor.r &&
           PALETTE[outIdx].g == notifyInnerColor.g &&
           PALETTE[outIdx].b == notifyInnerColor.b);
  notifyOuterColor = PALETTE[outIdx];
}

void resetNotify() {
  // Build the timeline once (both layers start fading out together; inner ends last).
  float innerInEnd = NOTIFY_INNER_IN;
  float outerInEnd = NOTIFY_OUTER_DELAY + NOTIFY_OUTER_IN;
  notifyFullAt      = max(innerInEnd, outerInEnd);
  notifyOutStart    = notifyFullAt + NOTIFY_HOLD;
  notifyOuterOutEnd = notifyOutStart + NOTIFY_OUTER_OUT;
  notifyInnerOutEnd = notifyOutStart + NOTIFY_INNER_OUT;
  notifyCycle       = max(notifyOuterOutEnd, notifyInnerOutEnd) + NOTIFY_GAP;

  notifyStartMs = millis();
  notifyPickColors();
}

void tickNotify() {
  float t = (millis() - notifyStartMs) / 1000.0f;
  if (t >= notifyCycle) {            // new cycle: reroll colors, reset clock
    notifyStartMs = millis();
    notifyPickColors();
    t = 0.0f;
  }

  float innerB = notifyEnvelope(t, 0.0f,                NOTIFY_INNER_IN,
                                   notifyOutStart,       NOTIFY_INNER_OUT);
  float outerB = notifyEnvelope(t, NOTIFY_OUTER_DELAY,  NOTIFY_OUTER_IN,
                                   notifyOutStart,       NOTIFY_OUTER_OUT);

  for (uint8_t i = 0; i < LED_COUNT; i++) {
    const Color &col = notifyIsInner(i) ? notifyInnerColor : notifyOuterColor;
    float br = notifyIsInner(i) ? innerB : outerB;
    strip.setPixelColor(i, strip.Color(
      notifyGamma(col.r / 255.0f * br),
      notifyGamma(col.g / 255.0f * br),
      notifyGamma(col.b / 255.0f * br)));
  }
  strip.show();
}

// Visual grid test: lights each (x,y) in coordinate order so you can confirm
// the mapping matches the physical panel. Blocking + uses delay() on purpose —
// it's a bring-up tool, run on demand via the "grid" serial command.
void gridVisualTest() {
  Serial.println(F("Grid visual test: expect a left-to-right, top-to-bottom raster."));
  strip.clear();
  strip.show();

  // Sweep every coordinate in raster order: (0,0),(1,0),(2,0),(3,0),(0,1)...
  for (uint8_t y = 0; y < GRID_H; y++) {
    for (uint8_t x = 0; x < GRID_W; x++) {
      strip.clear();
      gridSet(x, y, strip.Color(30, 30, 30));   // dim white, one pixel
      strip.show();
      Serial.print(F("lighting (x="));
      Serial.print(x); Serial.print(F(", y=")); Serial.print(y);
      Serial.print(F(") -> index ")); Serial.println(gridIndex(x, y));
      delay(350);
    }
  }

  // Then light the inner 2×2 so you can confirm the notify split.
  strip.clear();
  for (uint8_t i = 0; i < LED_COUNT; i++)
    if (notifyIsInner(i)) strip.setPixelColor(i, strip.Color(0, 30, 0));
  strip.show();
  Serial.println(F("Inner 2x2 shown (green). Should be the center square."));
  delay(1500);

  strip.clear();
  strip.show();
  Serial.println(F("Grid visual test complete."));
}

// ── Serial command handling ──────────────────────────────────────────────────

void startMode(const String &name) {
  if (name == "idle") {
    mode = MODE_IDLE;
    resetIdle();
  } else if (name == "notify") {
    mode = MODE_NOTIFY;
    resetNotify();
  }
}

void handleSerial() {
  static String buf;
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\n' || ch == '\r') {     // accept either terminator
      buf.trim();
      if (buf.length()) {
        if (buf.startsWith("start:")) {
          startMode(buf.substring(6));
        } else if (buf == "stop") {
          mode = MODE_STOP;
          strip.clear();
          strip.show();
        } else if (buf == "test") {
          // gridSelfTest();
          // gridVisualTest();
        }
      }
      buf = "";
    } else {
      buf += ch;
    }
  }
}

void setup() {
  Serial.begin(BAUD_RATE);
  strip.begin();
  strip.setBrightness(255);   // per-pixel brightness handled in the animations
  strip.show();
  randomSeed(analogRead(A0));
  resetIdle();
}

void loop() {
  handleSerial();

  if (mode == MODE_STOP) return;

  unsigned long now = millis();
  uint16_t interval = (mode == MODE_NOTIFY) ? NOTIFY_TICK_MS : IDLE_TICK_MS;
  if (now - lastTick >= interval) {
    lastTick = now;
    if (mode == MODE_IDLE)        tickIdle();
    else if (mode == MODE_NOTIFY) tickNotify();
  }
}
