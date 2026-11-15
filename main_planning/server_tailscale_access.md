# Real server Tailscale access

15 November 2026: installed Tailscale 1.104.7 on `originalpocserver`
(Ubuntu 24.04.5 LTS), reached by SSH at LAN address `192.168.0.143`
as `original_home_srv`. Used the official installer at
https://tailscale.com/install.sh. The `tailscaled` service is active and
enabled at boot.

Enrollment was initiated but requires the owner to authenticate using the
generated Tailscale login link. No tailnet address or VPN reachability has
been verified yet. To obtain the pending link again, run
`sudo tailscale up --timeout=20s` on the server.

After enrollment, check `tailscale status` and `tailscale ip -4`, then test
SSH from a computer signed into the same tailnet:
`ssh original_home_srv@<server-tailscale-ip>`.

No exit node, subnet routes, Tailscale SSH or public Funnel was configured.
Existing OpenSSH provides server login.

Connection credentials and local SSH tooling stay under the Git-ignored
`local/` directory. Do not commit credentials or Tailscale state files.
