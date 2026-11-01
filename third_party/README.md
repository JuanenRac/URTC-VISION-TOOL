# third_party

Copies of the official Melexis MLX90640, MLX90641 and MLX90642 libraries (Apache-2.0, each folder keeps its licence file). They are the same files the URTC firmware compiles for its expansion slave, vendored here so the thermal companion and a future sensor head use the proven driver instead of a second one.

`melexis.lock.json` holds the SHA-256 of every file. `python tools/check_shared_drivers.py` fails when a file differs, is missing or is not listed, and, when a checkout of URTC is next to this repository (or named by `URTC_DIR`), when a file differs from URTC's copy. After copying a fixed driver from URTC, run it with `--update`.

Nothing here is compiled into the firmware image yet: the sensor is read through the sensor link, and wiring the driver to an I2C bus needs the real board.
