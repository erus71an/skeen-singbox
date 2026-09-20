# Installation Plan

## 1. Prepare Keenetic

- Enable SSH access to the router.
- Install Entware in `/opt`.
- Make sure KeeneticOS exposes connection policies and `OpkgTun`.
- Create a Keenetic connection policy, for example `KeenSingBox`.
- Assign the target devices or segments to that policy in the Keenetic UI.

## 2. Install keen-singbox

Copy and unpack the release archive:

```sh
scp dist/keen-singbox-keenetic.tar.gz root@192.168.1.1:/tmp/
ssh root@192.168.1.1
mkdir -p /tmp/keen-singbox-install
tar -xzf /tmp/keen-singbox-keenetic.tar.gz -C /tmp/keen-singbox-install
cd /tmp/keen-singbox-install
sh keen-singbox install
```

This installs the normal default profile. Use the low-memory profile only for
weak routers:

```sh
sh keen-singbox install lowmem
```

If an older `/opt/etc/keen-singbox/config.json` already exists, `install` leaves
it unchanged. To replace the active config with the default profile and create
timestamped backups:

```sh
cd /tmp/keen-singbox-install
keen-singbox install-config default
```

The installer:

- installs minimal Entware dependencies;
- copies the CLI to `/opt/bin/keen-singbox`;
- copies selected profile templates to `/opt/etc/keen-singbox`;
- copies all bundled profiles to `/opt/etc/keen-singbox/templates`;
- installs `sing-box` as `/opt/bin/keen-singbox-core`;
- creates `/opt/etc/init.d/S99KeenSingBox`.

If the `sing-box` download hangs or fails, install the core separately:

```sh
SINGBOX_DOWNLOAD_MAX_TIME=60 keen-singbox install-singbox
```

The downloader tries SourceForge mirror first, then `dl.sing-box.org`, then
GitHub release assets. This avoids relying on GitHub from the router when the
router has poor CDN connectivity.

If GitHub/CDN access is unstable on the router, copy a matching `.ipk` manually:

```sh
scp sing-box_1.13.20_openwrt_aarch64_cortex-a53.ipk root@192.168.1.1:/tmp/
ssh root@192.168.1.1
SINGBOX_PACKAGE=/tmp/sing-box_1.13.20_openwrt_aarch64_cortex-a53.ipk \
  keen-singbox install-singbox
```

The `.ipk` architecture must match `opkg print-architecture` and the router CPU.

## 3. Configure

Edit `/opt/etc/keen-singbox/settings.json`:

- set `policy.name` to the Keenetic policy name or description;
- set `policy.table4` only if automatic policy-table detection fails;
- keep `runtime.dir` under `/tmp/keen-singbox`;
- keep `tun.interface_name` aligned with `config.json`.
- the normal `default` profile sets `tun.txqueuelen=2000`, matching SKeen for
  `opkgtun*` and improving behavior under YouTube/QUIC/UDP load;
- the `lowmem` profile keeps `tun.txqueuelen=0` to avoid changing the kernel
  queue length on very small routers.

For an already installed router, change only this field without replacing the
active sing-box config:

```sh
keen-singbox set-txqueuelen 2000
keen-singbox restart
```

Edit `/opt/etc/keen-singbox/config.json`:

- keep the TUN inbound with `auto_route=false`;
- replace the example `hysteria2`/`tuic` credentials with real proxy nodes;
- keep logs and cache under `/tmp/keen-singbox`;
- avoid remote rule sets on small routers unless they are really needed.

The default assumes Keenetic already has an `OpkgTun` connection with description
`SKeen0`, backed by linux interface `opkgtun0`. Keep `tun.name=SKeen0` in
`settings.json` and the sing-box TUN inbound `interface_name=opkgtun0`.

## 4. Validate And Start

```sh
keen-singbox doctor
keen-singbox validate
keen-singbox start
keen-singbox status
```

Expected result:

- `sing-box` is running;
- `OpkgTun` exists with the configured description;
- the policy table has a default route via the `opkgtunX` linux interface;
- `status` shows `TUN firewall: applied` when `iptables` is available;
- `status` shows `TUN firewall hook: installed`;
- `status` shows the sing-box TUN inbound and, when Clash API is enabled, the
  selected `proxy` outbound;
- `/opt` does not receive runtime logs or cache files.

If traffic still does not go through VPN, verify that `hysteria2` and `tuic` in
`/opt/etc/keen-singbox/config.json` contain real server names, passwords, ports,
and TLS settings for your proxy nodes.

## 5. Recovery

Stop routing through the policy:

```sh
keen-singbox stop
```

This removes only the policy-table default route, the `keen-singbox` netfilter
hook, the current TUN firewall rules, and stops `sing-box`. It does not delete
the Keenetic `OpkgTun` interface.

## 6. Policy Table Troubleshooting

If `keen-singbox validate` cannot find the table:

```sh
ndmc -c show ip policy
ip rule show
cat /opt/etc/keen-singbox/settings.json
```

Use the exact policy name in `policy.name`. If KeeneticOS does not expose the
table through policy output, set `policy.table4` explicitly to the lookup table
from `ip rule show`.

## 7. Low-memory Profile

Install with:

```sh
sh keen-singbox install lowmem
```

This profile keeps logs at `fatal/error`, uses DNS cache `512`, disables the
Clash API and remote rule sets, and starts with a direct-only selector until you
add real proxy outbounds.
