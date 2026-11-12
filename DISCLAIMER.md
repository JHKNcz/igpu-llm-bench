# Disclaimer

## Not affiliated

This is an independent measurement project. It is not affiliated with, endorsed
by, or supported by AMD, HP, the llama.cpp project, Unsloth, Qwen, or any other
vendor named in the repository. Product names and trademarks belong to their
owners.

## Measurements are one machine

Every number here was measured on one laptop:

- AMD Ryzen AI 9 HX 375, Radeon 890M (`gfx1150`), 32 GB LPDDR5X
- HP OmniBook Ultra 14, Ubuntu, kernel 7.0.0-43
- llama.cpp `f872b5911`, ROCm 10.0.0

Hardware revisions, BIOS versions, firmware, drivers, ambient temperature and
background load all change results. Numbers from this repository are not a
prediction for your machine. Treat them as a starting point and measure your own.

## Firmware changes carry risk

The instructions change UEFI firmware settings through the OS:

```bash
echo 7 | sudo tee /sys/class/drm/card*/device/uma/carveout
sudo amd-smi set -G 12
```

These are real firmware writes, not user-space preferences. Raising the VRAM
carve-out takes memory away from the host; a machine with too little host RAM
can become unstable, and running applications can be killed by the OOM killer.
Changing GTT requires a reboot and may affect what the GPU can map.

You are responsible for:

- saving your work before changing memory settings
- knowing how to reset the setting, including from UEFI if the system does not
  boot normally
- verifying the result with the commands in `docs/memory.md` before relying on it

If you are not comfortable with that, use the UEFI setup screen instead, or do
not change the setting.

## No warranty, no support

The code is MIT and the text is CC BY 4.0, both provided **as is**, without
warranty of any kind. There is no support commitment, no guarantee that a command
works on your hardware, and no guarantee that a measurement is correct.

If a number here is wrong, the useful thing to do is reproduce it and open an
issue with the command, the log and the hardware — not to rely on it.

## Model licences

Model weights are not included. Qwen and other model files carry their own
licences (Apache-2.0 for the Qwen models referenced here). Check the licence of
any model you download and run.

## Not advice

Nothing here is professional, legal, or hardware-modification advice. It is a
record of what was measured and what was observed on one machine.
