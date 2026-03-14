#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

#define LED_PIN    6
#define LED_COUNT  16

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

void setup() {
  Serial.begin(9600);
  strip.begin();
  strip.setBrightness(50);
  strip.show();
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();

    switch (cmd) {
      case 'r':  // all red
        for (int i = 0; i < LED_COUNT; i++)
          strip.setPixelColor(i, strip.Color(255, 0, 0));
        break;
      case 'g':  // all green
        for (int i = 0; i < LED_COUNT; i++)
          strip.setPixelColor(i, strip.Color(0, 255, 0));
        break;
      case 'b':  // all blue
        for (int i = 0; i < LED_COUNT; i++)
          strip.setPixelColor(i, strip.Color(0, 0, 255));
        break;
      case 'o':  // off
        strip.clear();
        break;
    }

    strip.show();
  }
}
