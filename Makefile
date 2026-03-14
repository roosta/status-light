.PHONY: build upload monitor clean

build:
	uv run pio run

upload:
	uv run pio run -t upload

monitor:
	uv run pio device monitor -b 115200

clean:
	uv run pio run -t clean
