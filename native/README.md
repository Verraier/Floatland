# Floatland native part

Normal start from the repository root: `python3 run.py`. No separate installation is required.
Hyprland 0.56.2; the ABI is checked before building and loading.

- `main.cpp` / `titlebar.cpp` — title bars, snap and restore.
- `tasks.hpp`, `switcher-*.hpp` — keyboard switcher (Alt+Tab) and its layout/preparation.
- `overview-*.hpp` — overview layout, filter and state machine.
- `*_test.cpp` — standalone logic tests, built by CMake.

A full build and check of the plugin requires Linux with Hyprland 0.56.2 headers.
License and origin: `LICENSE`, `NOTICE.md`, `LICENSE.hyprbars`.
