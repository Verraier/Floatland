#!/usr/bin/env python3
"""Read-only build check: exact 0.56.2 compositor and matching header ABI."""
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys


def check():
    running = json.loads(subprocess.check_output(["hyprctl", "-j", "version"], text=True))
    if running.get("version") != "0.56.2":
        raise ValueError("Native titlebars currently require Hyprland 0.56.2")
    flags = subprocess.check_output(["pkg-config", "--cflags-only-I", "hyprland"], text=True)
    roots = [Path(flag[2:]) for flag in shlex.split(flags) if flag.startswith("-I")]
    roots += [Path(subprocess.check_output(["pkg-config", "--variable=includedir", "hyprland"], text=True).strip()),
              Path("/usr/include")]
    header = next((root / "hyprland/src/version.h" for root in roots
                   if (root / "hyprland/src/version.h").is_file()), None)
    if header is None:
        raise ValueError("Missing Hyprland development headers (version.h)")
    defines = dict(re.findall(r'^#define\s+(\w+)\s+"([^"\n]*)"', header.read_text(), re.M))
    abi = defines["GIT_COMMIT_HASH"]
    for short, name in (("aq", "AQUAMARINE"), ("hu", "HYPRUTILS"), ("hg", "HYPRGRAPHICS"),
                        ("hc", "HYPRCURSOR"), ("hlg", "HYPRLANG")):
        version = defines[name + "_VERSION"]
        abi += "_" + short + "_" + version.rsplit(".", 1)[0]
    if abi != running["abiHash"]:
        raise ValueError("Header ABI differs from running compositor; install matching headers before building")
    print("Hyprland 0.56.2 and development-header ABI match")


if __name__ == "__main__":
    try:
        check()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("floatland titlebars: " + str(error), file=sys.stderr)
        sys.exit(1)
