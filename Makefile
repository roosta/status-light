.PHONY: build upload monitor clean

build:
	uv run pio run

upload:
	uv run pio run -t upload

monitor:
	uv run pio device monitor -b 9600

clean:
	uv run pio run -t clean
