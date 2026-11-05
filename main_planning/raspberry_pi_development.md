# Raspberry Pi development host

Development moved to `192.168.1.122` on 5 November 2026. SSH user: `original_volt_gateway`. Passwords are not stored in project files.

- Hardware: Raspberry Pi 4 Model B Rev 1.5, about 4 GB RAM, aarch64.
- Python: 3.13.5.
- Project: `/home/original_volt_gateway/OriginalHomeIOT`.
- Existing OpenEMS installation: `/home/original_volt_gateway/original`; `original-edge.service` is active. Existing nginx UI listens on port 80. These services are preserved.
- New gateway development service: user unit `originalhome-gateway.service`, bound to `127.0.0.1:8080`, now reading the running OpenEMS REST API at `127.0.0.1:8084`. The UI labels the upstream as an OpenEMS demo system. No equipment writes or ThingsBoard delivery configured.
- Private integration configuration: `~/.config/originalhome/gateway.env` (mode 0600), loaded by the service drop-in `~/.config/systemd/user/originalhome-gateway.service.d/openems.conf`. This file contains credentials and is not part of the repository. The local UI uses `admin` with a separately generated password stored in that file.
- Verified all five mapped energy channels with W/% units, fresh persisted samples, authentication rejection (401), and rejected control requests (405). Six tests pass on the Pi. Equipment communication and real inverter behavior are not qualified by this demo integration.

Access from the development computer with an SSH tunnel:

```powershell
ssh -N -L 8080:127.0.0.1:8080 original_volt_gateway@192.168.1.122
```

Then browse to http://127.0.0.1:8080. The tunnel must remain open. This does not replace the existing UI at http://192.168.1.122.

On the Pi:

```sh
cd ~/OriginalHomeIOT
python3 -m unittest discover -s tests -v
systemctl --user status originalhome-gateway
systemctl --user restart originalhome-gateway
journalctl --user -u originalhome-gateway -n 50 --no-pager
```

Install the user unit from `tools/originalhome-gateway.service` into `~/.config/systemd/user/`, then run `systemctl --user daemon-reload` and `systemctl --user enable --now originalhome-gateway`. User services start with the user manager; unattended boot requires a separately configured lingering/login policy. No boot-persistence claim is made here.

The transfer includes working source, tests, tools, planning documents and Git history. Generated caches, runtime databases and local credential/configuration directories are excluded. Subsequent development should be executed and tested on the Pi; keep source changes synchronized with the workspace deliberately.
