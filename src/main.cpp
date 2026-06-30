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

// ── Idle animation ───────────────────────────────────────────────────────────
// Random pixels fade in to a random palette color, hold, then fade out.

const Color IDLE_PALETTE[] = {
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
const uint8_t IDLE_PALETTE_SIZE = sizeof(IDLE_PALETTE) / sizeof(IDLE_PALETTE[0]);

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
      idleCells[idx].color     = IDLE_PALETTE[random(IDLE_PALETTE_SIZE)];
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
// TODO: placeholder — replace with the real notification animation. For now it
// is a slow green pulse across all pixels so the pipeline is testable.

const Color    NOTIFY_COLOR   = {10, 230, 30};   // green
const uint8_t  NOTIFY_STEPS   = 30;
const uint16_t NOTIFY_TICK_MS = 1000 / 30;
uint8_t notifyStep = 0;
int8_t  notifyDir  = 1;

void resetNotify() {
  notifyStep = 0;
  notifyDir  = 1;
}

void tickNotify() {
  float br = (float)notifyStep / NOTIFY_STEPS;
  for (uint8_t i = 0; i < LED_COUNT; i++)
    strip.setPixelColor(i, strip.Color(NOTIFY_COLOR.r * br, NOTIFY_COLOR.g * br, NOTIFY_COLOR.b * br));
  strip.show();

  notifyStep += notifyDir;
  if (notifyStep == NOTIFY_STEPS || notifyStep == 0) notifyDir = -notifyDir;
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
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();

  if (line.startsWith("start:")) {
    startMode(line.substring(6));
  } else if (line == "stop") {
    mode = MODE_STOP;
    strip.clear();
    strip.show();
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
