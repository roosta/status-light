#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

#define LED_PIN   6
#define LED_COUNT 16
#define BAUD_RATE 115200

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

void parseFrame(String data) {
  // data: "RRGGBB,RRGGBB,..." (16 entries)
  int idx = 0;
  int start = 0;

  while (idx < LED_COUNT) {
    int comma = data.indexOf(',', start);
    String hex = (comma == -1) ? data.substring(start) : data.substring(start, comma);

    if (hex.length() >= 6) {
      uint8_t r = strtol(hex.substring(0, 2).c_str(), nullptr, 16);
      uint8_t g = strtol(hex.substring(2, 4).c_str(), nullptr, 16);
      uint8_t b = strtol(hex.substring(4, 6).c_str(), nullptr, 16);
      strip.setPixelColor(idx, strip.Color(r, g, b));
    }

    start = comma + 1;
    idx++;
    if (comma == -1) break;
  }

  strip.show();
}

void setup() {
  Serial.begin(BAUD_RATE);
  strip.begin();
  strip.setBrightness(255); // brightness handled in Python
  strip.show();
}

void loop() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();

    if (line.startsWith("F:")) {
      parseFrame(line.substring(2));
    } else if (line == "C") {
      strip.clear();
      strip.show();
    }
  }
}
