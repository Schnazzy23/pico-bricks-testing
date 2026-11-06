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

These folders are a suggested layout; this repository currently starts with this README.

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

Repository initialized. Hardware experiments and results will be added as testing progresses.
