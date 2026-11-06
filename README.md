# PicoBricks Testing

A workspace for Raspberry Pi Pico and PicoBricks experiments, component checks, and learning projects.

## Goals

- Try small, focused experiments with LEDs, buttons, sensors, displays, and other modules.
- Keep working examples alongside wiring notes and observations.
- Record what worked, what failed, and what to try next.

## Getting started

1. Record your Pico model, PicoBricks board revision, and chosen programming environment.
2. Set up the firmware and tools appropriate to your board and language.
3. Start with one component at a time and confirm its pin assignments against your board documentation.
4. Add an experiment with its code, required libraries, connection details, and expected behavior.
5. Run it on the hardware and record the actual results.

For MicroPython experiments, use an editor or upload tool that can connect to the Pico, then copy the required files to the board and run the experiment.

## Suggested organization

As experiments are added, use a structure like this:

```text
experiments/
  01-led/
    main.py
    README.md
  02-button/
    main.py
    README.md
docs/
  hardware.md
  test-log.md
```

The weather-station and fan experiments use the folders described below.

## Experiment notes

For each experiment, document:

- **Purpose:** What are you testing?
- **Hardware:** Pico model, PicoBricks revision, and connected modules.
- **Software:** Language, firmware version, and required libraries.
- **Connections:** Pin assignments and any wiring changes.
- **Run steps:** How to load and start the code.
- **Expected result:** What should happen?
- **Observed result:** What happened, including errors or unexpected behavior.
- **Status:** Untested, working, or needs investigation.

## Initial experiment ideas

- Blink an LED.
- Read a button and report its state.
- Read a sensor and log values.
- Show a message on a display.
- Combine a sensor input with an output.

## Hardware testing

Disconnect power before changing wiring, and verify voltage requirements and pin assignments for the exact hardware in use. Keep credentials and other private configuration out of this public repository.

## Project status

The weather-station experiment includes a local dashboard with temperature, humidity,
heat index, saved history, graph tooltips, and authenticated Auto / On / Off relay
controls. Low-temperature indicators are blue at 16 degrees Celsius and below.

See [Weather station setup](experiments/weather-station/README.md) for instructions.
The relay helper is in [fan_starter.py](experiments/fan/fan_starter.py).

## Private configuration

Copy `experiments/weather-station/pico_config.example.py` to `pico_config.py`,
fill it privately, and save it alongside `main.py` on the Pico. Never commit the
filled configuration. Server upload and control keys come from environment variables.
Databases, logs, private configs, and preview data are excluded by `.gitignore`.

The webserver remains a trusted-LAN/private-VPN prototype, not a public internet
service. Relay state reports the Pico output, not physical fan-speed feedback.

## Checks

From the repository root:

```bash
python3 -m unittest discover -s tests
```

Pico tests use simulated hardware and do not actuate a real relay.

