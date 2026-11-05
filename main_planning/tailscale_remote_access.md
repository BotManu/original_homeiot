# Pi remote access through Tailscale

Installed on 5 November 2026 using Tailscale's official Linux installer and stable Debian trixie package repository. Version observed: 1.104.5, arm64. `tailscaled.service` is active and enabled at boot.

Owner approved enrollment on 5 November 2026. Verified state: `Running`, online, no reported health warnings. Pi IPv4: `100.65.109.74`; DNS name: `original-volt-gateway.tail2b4e58.ts.net`. Tailscale ping and an OpenSSH login from the development computer succeeded. OriginalHome's authentication endpoint was reached through the SSH tunnel (HTTP 401 without credentials). This test ran on the current LAN; a different-network test remains outstanding. No auth keys or account credentials are stored in the project.

Use a client signed into the same tailnet, subject to its access policy. Existing OpenSSH remains the SSH server; Tailscale SSH, exit-node advertisement, subnet routes and public Funnel access were not enabled.

```sh
ssh original_volt_gateway@100.65.109.74
```

OriginalHome is now available directly at http://100.65.109.74/ and http://original-volt-gateway.tail2b4e58.ts.net/ using its existing UI credentials (`admin` and the gateway password). On 5 November 2026, installed `tools/originalhome-tailscale.nginx` into `/etc/nginx/sites-available/originalhome-tailscale` and enabled it through `sites-enabled`. Nginx routes these hostnames to the loopback gateway on port 8080; the default OpenEMS LAN UI remains unchanged. Configuration validation and reload succeeded. Authenticated UI, assets, commissioning API and overview returned HTTP 200; the source was connected with fresh simulated OpenEMS data. The remote unauthenticated URL returns OriginalHome's HTTP 401 challenge.

The gateway remains bound to the Pi's loopback address. An SSH tunnel is also available:

```sh
ssh -N -L 8082:127.0.0.1:8080 original_volt_gateway@100.65.109.74
```

Open http://127.0.0.1:8082 on the client and use the OriginalHome UI credentials. This uses local port 8082 to avoid conflicting with the existing development LAN tunnel on port 8080. The tunnel must remain open.

Tailscale needs network connectivity at the installation site. Test it from outside the site's LAN before relying on it. The gateway user service is enabled and `loginctl enable-linger original_volt_gateway` was applied on 5 November 2026 (`Linger=yes`) for startup without an interactive login. An actual reboot recovery test remains outstanding. Tailscale node approval, device-key expiry and permitted access are managed in the owner's tailnet.

Reference: [Install Tailscale on Linux](https://tailscale.com/docs/install/linux).
