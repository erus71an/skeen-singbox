# keen-singbox

Standalone Keenetic + Entware runner for `sing-box` through Keenetic connection
policies and an `OpkgTun` interface. It does not install or modify SKeen files.

The default install uses the normal profile adapted from the older SKeen managed
OpkgTun config: existing `SKeen0`/`opkgtun0`, policy lookup by description
`SKeen`, Clash API on port `9999`, DNS cache, `hysteria2` + `tuic` outbounds
behind a `proxy` urltest, and the same practical route/rule-set layout.

The low-memory profile is available separately for weak routers. The resource
model is intentionally conservative in both profiles:

- static files only in `/opt`;
- logs, cache, downloads, and unpacking in `/tmp/keen-singbox`;
- no `ipset` dependency by default;
- only minimal `iptables` TUN rules are applied when `iptables` is present;
- no writes to `/opt` during normal runtime;
- IPv4-only DNS by default.

## Installed Paths

```text
/opt/bin/keen-singbox
/opt/bin/keen-singbox-core
/opt/etc/keen-singbox/settings.json
/opt/etc/keen-singbox/config.json
/opt/etc/keen-singbox/templates/
/opt/etc/init.d/S99KeenSingBox
/opt/etc/ndm/netfilter.d/keen-singbox-firewall.sh
/tmp/keen-singbox/
```

## Install From Release Archive

Copy `dist/keen-singbox-keenetic.tar.gz` to the router:

```sh
scp dist/keen-singbox-keenetic.tar.gz root@192.168.1.1:/tmp/
```

Install the normal default profile on Keenetic:

```sh
ssh root@192.168.1.1
mkdir -p /tmp/keen-singbox-install
tar -xzf /tmp/keen-singbox-keenetic.tar.gz -C /tmp/keen-singbox-install
cd /tmp/keen-singbox-install
sh keen-singbox install
```

Install the low-memory profile only when RAM is tight:

```sh
sh keen-singbox install lowmem
```

or:

```sh
KEEN_SINGBOX_PROFILE=lowmem sh keen-singbox install
```

`install` is conservative: if `/opt/etc/keen-singbox/config.json` already
exists, it is left unchanged. Profile templates are copied to
`/opt/etc/keen-singbox/templates/`, and the selected profile is also copied as
an example beside the active files.
To intentionally replace the active settings and config with backups:

```sh
keen-singbox install-config default
```

For lowmem:

```sh
keen-singbox install-config lowmem
```

For a pinned `sing-box` version:

```sh
SINGBOX_VERSION=1.12.0 sh keen-singbox install-singbox
```

If the router cannot download from GitHub or the default mirror, use an explicit
URL:

```sh
SINGBOX_URL="https://example.com/sing-box_1.13.20_openwrt_aarch64_cortex-a53.ipk" \
  keen-singbox install-singbox
```

Or copy the `.ipk` package to the router first and install from the local file:

```sh
scp sing-box_1.13.20_openwrt_aarch64_cortex-a53.ipk root@192.168.1.1:/tmp/
ssh root@192.168.1.1
SINGBOX_PACKAGE=/tmp/sing-box_1.13.20_openwrt_aarch64_cortex-a53.ipk \
  keen-singbox install-singbox
```

Downloads use conservative curl limits by default: 15 seconds to connect and
180 seconds total per URL. Override them only when the router has a very slow
link:

```sh
SINGBOX_DOWNLOAD_MAX_TIME=300 keen-singbox install-singbox
```

By default, the downloader tries SourceForge mirror first, then
`dl.sing-box.org`, then GitHub release assets. To use another mirror that stores
files as `<base>/v<version>/<package>/download`:

```sh
SINGBOX_MIRROR_BASE="https://sourceforge.net/projects/sing-box.mirror/files" \
  keen-singbox install-singbox
```

## Configure

Edit:

```text
/opt/etc/keen-singbox/settings.json
/opt/etc/keen-singbox/config.json
```

In `settings.json`, set `policy.name` to the exact Keenetic connection policy
name or description. The default is `SKeen`, so it matches a Keenetic policy
shown as `policy, name = Policy0, description = SKeen`. Create and assign
devices or segments to that policy in the Keenetic web UI. `keen-singbox` only
connects the policy table to `OpkgTun`; it does not manage policy membership.

In `config.json`, replace the default example `hysteria2` and `tuic` credentials
with your real proxy nodes. The shipped normal profile is structurally ready for
VPN routing, but the server names, UUIDs, passwords, and ports must be yours.

Default outbound layout:

```json
[
  {
    "type": "urltest",
    "tag": "proxy",
    "outbounds": ["hysteria2", "tuic"]
  },
  {
    "type": "hysteria2",
    "tag": "hysteria2"
  },
  {
    "type": "tuic",
    "tag": "tuic"
  }
]
```

You may replace these with `vless`, `trojan`, or another sing-box outbound, but
keep the route target `"tag": "proxy"` or update route rules accordingly.

Keep the TUN inbound aligned with `settings.json`:

```json
{
  "type": "tun",
  "address": "172.19.0.1/30",
  "auto_route": false,
  "interface_name": "opkgtun0"
}
```

The default assumes Keenetic already has an `OpkgTun` connection with description
`SKeen0`, backed by linux interface `opkgtun0`. Keep both files aligned:

```json
// /opt/etc/keen-singbox/settings.json
"tun": {
  "name": "SKeen0",
  "interface_name": "opkgtun0"
}
```

```json
// /opt/etc/keen-singbox/config.json
"inbounds": [
  {
    "type": "tun",
    "interface_name": "opkgtun0"
  }
]
```

Then run:

```sh
keen-singbox validate
keen-singbox restart
```

## Operate

```sh
keen-singbox validate
keen-singbox start
keen-singbox status
keen-singbox reload
keen-singbox restart
keen-singbox stop
keen-singbox logs
keen-singbox clean-runtime
keen-singbox doctor
keen-singbox install-init
```

The service commands use a runtime lock, so concurrent boot and manual restart
cannot remove each other's PID, route, or firewall state. The PID check also
verifies that the process command line belongs to the configured sing-box core.
Set `KEEN_SINGBOX_PID_STRICT=0` only for diagnostics with a synthetic PID file.

`validate`, `start`, and `reload` run `sing-box check` before changing runtime
state. `stop` removes only the default route from the policy table and stops
`sing-box`; the Keenetic `OpkgTun` interface is intentionally kept to avoid
rewriting router configuration on every service cycle.

`status` also reports the sing-box TUN inbound, current `proxy` outbound from
the Clash API when it is enabled, and a one-second RX/TX traffic sample from the
linux TUN interface. On lowmem or configs without Clash API, `VPN outbound` is
shown as `not available`.

## Troubleshooting

If `keen-singbox start` succeeds but VPN traffic does not work, check these
first:

```sh
keen-singbox status
ip route show table 4096
cat /opt/etc/keen-singbox/config.json
```

The default route in the policy table must point to `opkgtun0`, and the
`hysteria2`/`tuic` example nodes must contain your real proxy credentials.
`VPN outbound` should show the selected node from sing-box, for example
`selected=hysteria2`. `Traffic` should change when a client assigned to the
policy opens proxied traffic.

`TUN firewall` should show `applied` when `iptables` is available. These are the
minimal SKeen-style OpkgTun rules: accept `opkgtun0` traffic through a dedicated
chain and masquerade traffic leaving via `opkgtun0`. Disable them only with
`"firewall": { "tun_rules_enabled": 0 }` in `settings.json`.

`TUN firewall hook` should show `installed`. The hook re-applies the same
minimal rules when Keenetic rebuilds netfilter tables after interface, policy,
or firewall changes. `keen-singbox stop` removes the hook and the current rules.

Keenetic connection policies can route a client through the IPv4 OpkgTun while
the same client still reaches the Internet directly over IPv6. For devices that
must stay on the IPv4 policy, list their MAC addresses in `settings.json`:

```json
"firewall": {
  "tun_rules_enabled": 1,
  "ipv6_block_macs": [
    "02:00:00:00:00:01"
  ]
}
```

After `keen-singbox restart`, the wrapper creates its own `ip6tables` chain and
rejects forwarded IPv6 traffic only for those clients, causing them to use IPv4.
The managed jump is kept first in `FORWARD` so Keenetic's broader accept rules
cannot bypass the client block.
`status` and `doctor` report `IPv6 client block: applied`; the firewall hook
restores the rules after Keenetic rebuilds netfilter state. An empty list leaves
IPv6 unchanged for every client.

If startup stops at `Failed to add iptables nat rule`, the process may already
be running while firewall and policy routing are still incomplete. Older
versions required `xt_comment` to label the NAT rule; if that module was not
loaded after reboot, iptables could report `No chain/target/match by that name`.
The current version uses the private NAT chain `keen_singbox_nat` without that
dependency. It removes the old tagged rule after installing its replacement,
and preserves unrelated NAT rules. Other missing NAT targets or tables still
cause a startup error, now including the exact failed rule.

After copying the updated CLI to `/tmp/keen-singbox.new`, update the runner
and autostart script without replacing your settings, proxy credentials or core:

```sh
sh -n /tmp/keen-singbox.new &&
cp -p /opt/bin/keen-singbox /opt/bin/keen-singbox.before-reboot-fix &&
cp /tmp/keen-singbox.new /opt/bin/keen-singbox &&
chmod 755 /opt/bin/keen-singbox &&
keen-singbox install-init &&
keen-singbox restart &&
keen-singbox doctor
```

`install-init` installs or refreshes `/opt/etc/init.d/S99KeenSingBox`. It honors
`start`, `stop`, `restart`, `reload`, and `status`; boot-time `start` uses
`auto_start.enabled` and `auto_start.delay` from settings. Boot output is appended
to `/tmp/keen-singbox/init.log`, including stderr and failures before the wrapper
logger runs. `doctor` checks whether autostart is enabled and the init script
is executable. To investigate another boot failure, collect:

```sh
cat /tmp/keen-singbox/init.log
keen-singbox logs
keen-singbox doctor
```

A complete startup ends with `Service startup completed`. For the default
policy table, the expected route is `default dev opkgtun0 ... metric 10`, without
`via 172.19.0.1`. `Running: yes` alone only confirms that the tracked core process
exists; also check the firewall, hook and route statuses.

After the first route installation, the service waits two seconds and verifies
the policy table again. Override this with
`KEEN_SINGBOX_ROUTE_RECHECK_SECONDS=0` only when running a controlled test.

Wrapper logs are rotated at 512 KiB and two backups are kept by default. Adjust
`KEEN_SINGBOX_LOG_MAX_BYTES` and `KEEN_SINGBOX_LOG_BACKUPS` for a different
runtime budget. The sing-box log is also rotated before each managed start;
`keen-singbox logs` shows the current wrapper and core logs.

The profile settings pin sing-box to version `1.13.20`. `keen-singbox install-singbox`
uses that version unless `SINGBOX_VERSION` is explicitly supplied. `doctor`
reports a version mismatch before an upgrade is used in production.

`keen-singbox install-config` stages each JSON file as a temporary file, validates
it, backs up the active file, and activates it with an atomic rename. A malformed
template therefore cannot replace the working configuration.

When firewall setup is incomplete, `doctor` reports the missing filter or NAT
chain and whether the `MASQUERADE` target is visible. This makes a missing
Keenetic kernel module distinguishable from an ordinary stale rule. The service
hook still re-applies the owned chains after Keenetic rebuilds netfilter state.

`tun.txqueuelen` controls the Linux transmit queue for `opkgtun0`. The normal
`default` profile uses `2000`, matching SKeen behavior for `opkgtun*`; this is
usually better for YouTube/QUIC and other UDP-heavy traffic. The `lowmem`
profile keeps `0`, which means `keen-singbox` does not change the interface
queue length.

If the tunnel is connected but video stutters or behaves like packets are being
dropped, use `1000` or `2000`. If the router is very RAM-constrained or latency
gets worse on a saturated link, return it to `0`:

```sh
keen-singbox set-txqueuelen 2000
keen-singbox restart
keen-singbox status
```

```json
"tun": {
  "txqueuelen": 2000
}
```

If `cache_capacity` is `512` and there are no `hysteria2`/`tuic` outbounds, the
router is still using the old lowmem config. Replace the active config:

```sh
cd /tmp/keen-singbox-install
keen-singbox install-config default
keen-singbox validate
keen-singbox restart
```

If validation reports:

```text
Connection policy '<name>' table was not found; set policy.table4
```

check the policy name and table on the router:

```sh
ndmc -c show ip policy
ip rule show
cat /opt/etc/keen-singbox/settings.json
```

Then either set `policy.name` to the exact Keenetic connection policy name, or
set `policy.table4` manually in `/opt/etc/keen-singbox/settings.json` to the
table shown by `ndmc`/`ip rule`.

If manual `sing-box` start reports:

```text
initialize cache-file: timeout
```

first stop the managed service and check for a stale process that still owns the
cache file:

```sh
keen-singbox stop
keen-singbox clean-runtime
ps | grep '[s]ing-box'
keen-singbox doctor
```

The manager tracks the PID file and uses it for `stop`, so it should release the
old process and the `/tmp/keen-singbox/cache.db` lock. On start, if this exact
cache timeout is detected, `keen-singbox` removes only the runtime cache under
`/tmp` and retries once automatically.

## Low-memory Profile

Use `lowmem` when the router has little RAM or slow USB storage:

```sh
sh keen-singbox install lowmem
```

Lowmem differences:

- `fatal` sing-box logs and `error` wrapper logs;
- DNS cache capacity `512`;
- no Clash API;
- no remote rule sets;
- selector defaults to `direct` until you add real proxy outbounds;
- autostart delay `30` seconds.

## Build

From this repository:

```sh
sh scripts/build-release.sh
```

The archive is written to:

```text
dist/keen-singbox-keenetic.tar.gz
```

## Attribution

The Keenetic `OpkgTun` and policy-table handling is inspired by SKeen and its
managed OpkgTun companion. SKeen is MIT-licensed; keep this attribution if code
is redistributed.
