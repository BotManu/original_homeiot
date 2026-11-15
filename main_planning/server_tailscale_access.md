# Real server Tailscale access

15 November 2026: installed Tailscale 1.104.7 on `originalpocserver`
(Ubuntu 24.04.5 LTS), reached by SSH at LAN address `192.168.0.143`
as `original_home_srv`. Used the official installer at
https://tailscale.com/install.sh. The `tailscaled` service is active and
enabled at boot.

Owner completed enrollment on 15 November 2026. Verified over LAN SSH:
`tailscale ip -4` returns `100.122.80.43`, `tailscale status` lists
`originalpocserver` in the owner's tailnet, and `tailscaled` is active.
The initial VPN SSH attempt timed out while the development client's
Tailscale service was starting. On 15 November 2026, subsequent authenticated
SSH sessions through `100.122.80.43` succeeded during the cloud PoC deployment.

After enrollment, check `tailscale status` and `tailscale ip -4`, then test
SSH from a computer signed into the same tailnet:
`ssh original_home_srv@100.122.80.43`.

No exit node, subnet routes, Tailscale SSH or public Funnel was configured.
Existing OpenSSH provides server login.

Connection credentials and local SSH tooling stay under the Git-ignored
`local/` directory. Do not commit credentials or Tailscale state files.

The private cloud monitoring PoC is documented in
[deployment runbook](../deploy/poc/README.md).
