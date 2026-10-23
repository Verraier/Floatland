# Local shell API, version 1

Floatland is usable without a shell. A shell may query the daemon's per-Hyprland-instance Unix socket, `floatland.sock`, in the same directory as the Hyprland sockets. `python3 run.py windows` exposes the same list for inspection.

Send one newline-terminated JSON request per connection. Read a newline-terminated response. Success is `{ "ok": true, "result": ... }`; failure is `{ "ok": false, "error": "..." }`.

```json
{"action":"windows"}
{"action":"close","target":"0x1234","pid":12345}
{"action":"pin-above","target":"0x1234","pid":12345}
{"action":"snap","value":"left","target":"0x1234","pid":12345}
```

The windows result contains api_version=1 and windows with address, pid, class, title, workspace, floating, pinned, above and minimized. Use the returned address and PID together. Addressed commands reject stale identities instead of acting on the focused window. Addresses/PIDs are session identities, not persistent application IDs.

There is no dedicated Floatland event subscription yet. A shell can listen to Hyprland socket2 changes and re-query the list; event payloads are not a stable Floatland API. Do not read or mutate private daemon state files as an integration mechanism.
