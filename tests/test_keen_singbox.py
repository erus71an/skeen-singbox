from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "keen-singbox"
SETTINGS = ROOT / "examples" / "settings.lowmem.json"
CONFIG = ROOT / "examples" / "config.lowmem.json"
DEFAULT_SETTINGS = ROOT / "examples" / "settings.default.json"
DEFAULT_CONFIG = ROOT / "examples" / "config.default.json"


def make_jsonfilter(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    jsonfilter = bin_dir / "jsonfilter"
    implementation = bin_dir / "jsonfilter.py"
    implementation.write_text(
        """
import json
import sys

args = sys.argv[1:]
path = None
expr = None
while args:
    arg = args.pop(0)
    if arg == "-i":
        path = args.pop(0)
    elif arg == "-e":
        expr = args.pop(0)

if not path or not expr:
    sys.exit(1)

with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

if expr == "@":
    print(json.dumps(data))
    sys.exit(0)

if expr == '@.route.rule_set[@.type="remote"].url':
    for item in data.get("route", {}).get("rule_set", []):
        if item.get("type") == "remote" and item.get("url") is not None:
            print(item["url"])
    sys.exit(0)

if expr == '@.firewall.ipv6_block_macs[*]':
    for item in data.get("firewall", {}).get("ipv6_block_macs", []):
        print(item)
    sys.exit(0)

if expr.startswith('@.inbounds[@.type="tun"].'):
    field = expr.rsplit(".", 1)[-1]
    for item in data.get("inbounds", []):
        if item.get("type") == "tun" and item.get(field) is not None:
            value = item[field]
            if isinstance(value, bool):
                print("true" if value else "false")
            else:
                print(value)
            sys.exit(0)
    sys.exit(1)

if not expr.startswith("@."):
    sys.exit(1)

value = data
for part in expr[2:].split("."):
    if isinstance(value, dict) and part in value:
        value = value[part]
    else:
        sys.exit(1)

if isinstance(value, bool):
    print("true" if value else "false")
elif value is not None:
    print(value)
""",
        encoding="utf-8",
    )
    jsonfilter.write_text(
        "#!/bin/sh\n"
        f"exec {shlex.quote(sys.executable)} "
        f"{shlex.quote(str(implementation))} \"$@\"\n",
        encoding="utf-8",
    )
    jsonfilter.chmod(0o755)
    return bin_dir


def make_iptables(tmp_path: Path, check_status: int = 1) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    iptables = bin_dir / "iptables"
    iptables.write_text(
        f"""#!/bin/sh
printf '%s\\n' "$*" >> "$IPTABLES_LOG"
case " $* " in
  *" -C "*) exit {check_status} ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    iptables.chmod(0o755)
    return iptables


def make_ip6tables(tmp_path: Path, check_status: int = 1) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    ip6tables = bin_dir / "ip6tables"
    ip6tables.write_text(
        f"""#!/bin/sh
printf '%s\\n' "$*" >> "$IP6TABLES_LOG"
case " $* " in
  *" -C "*) exit {check_status} ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    ip6tables.chmod(0o755)
    return ip6tables


def make_ip(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    ip = bin_dir / "ip"
    ip.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$IP_LOG"
exit 0
""",
        encoding="utf-8",
    )
    ip.chmod(0o755)
    return ip


def make_ndmc(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    ndmc = bin_dir / "ndmc"
    ndmc.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$NDMC_LOG"
exit 0
""",
        encoding="utf-8",
    )
    ndmc.chmod(0o755)
    return ndmc


def make_singbox_core(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    core = bin_dir / "keen-singbox-core"
    core.write_text(
        """#!/bin/sh
case "${1:-}" in
  version)
    echo "sing-box version test"
    ;;
  check)
    exit 0
    ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    core.chmod(0o755)
    return core


def run_script(
    tmp_path: Path, action: str, **env: str
) -> subprocess.CompletedProcess[str]:
    bin_dir = make_jsonfilter(tmp_path)
    merged_env = os.environ.copy()
    merged_env.update(
        {
            "KEEN_SINGBOX_SETTINGS": str(SETTINGS),
            "KEEN_SINGBOX_DRY_RUN": "1",
            "KEEN_SINGBOX_JSONFILTER": str(bin_dir / "jsonfilter"),
            "PATH": f"{bin_dir}:{merged_env['PATH']}",
        }
    )
    merged_env.update(env)
    return subprocess.run(
        ["sh", str(SCRIPT), action],
        capture_output=True,
        check=False,
        env=merged_env,
        text=True,
    )


def test_install_config_can_use_templates_from_current_directory(
    tmp_path: Path,
) -> None:
    bin_dir = make_jsonfilter(tmp_path)
    work_dir = tmp_path / "work"
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    for name in (
        "settings.default.json",
        "config.default.json",
        "settings.lowmem.json",
        "config.lowmem.json",
    ):
        source = ROOT / "examples" / name
        (install_dir / name).write_text(
            source.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    env = os.environ.copy()
    env.update(
        {
            "KEEN_SINGBOX_WORK_DIR": str(work_dir),
            "KEEN_SINGBOX_SETTINGS": str(work_dir / "settings.json"),
            "KEEN_SINGBOX_CONFIG": str(work_dir / "config.json"),
            "KEEN_SINGBOX_JSONFILTER": str(bin_dir / "jsonfilter"),
        }
    )

    result = subprocess.run(
        ["sh", str(SCRIPT), "install-config", "default"],
        capture_output=True,
        check=False,
        cwd=install_dir,
        env=env,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads((work_dir / "settings.json").read_text())["profile"] == "default"
    assert (
        json.loads((work_dir / "config.json").read_text())["dns"]["cache_capacity"]
        == 1024
    )


def test_shell_syntax() -> None:
    result = subprocess.run(
        ["sh", "-n", str(SCRIPT)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_lowmem_template_keeps_runtime_in_tmp() -> None:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    tun_inbound = next(item for item in config["inbounds"] if item["type"] == "tun")

    assert settings["runtime"]["dir"].startswith("/tmp/")
    assert settings["firewall"]["tun_rules_enabled"] == 1
    assert settings["firewall"]["ipv6_block_macs"] == []
    assert settings["tun"]["txqueuelen"] == 0
    assert config["log"]["output"].startswith("/tmp/")
    assert config["experimental"]["cache_file"]["path"].startswith("/tmp/")
    assert tun_inbound["auto_route"] is False
    assert tun_inbound["interface_name"] == settings["tun"]["interface_name"]
    assert config["dns"]["strategy"] == "ipv4_only"
    assert "rule_set" not in config["route"]


def test_default_template_is_not_direct_only_lowmem() -> None:
    settings = json.loads(DEFAULT_SETTINGS.read_text(encoding="utf-8"))
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    tun_inbound = next(item for item in config["inbounds"] if item["type"] == "tun")
    outbound_tags = {item["tag"] for item in config["outbounds"]}
    proxy = next(item for item in config["outbounds"] if item["tag"] == "proxy")
    geosite_rule = next(
        item
        for item in config["route"]["rules"]
        if "rule_set" in item and "youtube-geosite" in item["rule_set"]
    )

    assert settings["profile"] == "default"
    assert settings["policy"]["name"] == "SKeen"
    assert settings["tun"]["name"] == "SKeen0"
    assert settings["tun"]["interface_name"] == "opkgtun0"
    assert settings["firewall"]["tun_rules_enabled"] == 1
    assert settings["firewall"]["ipv6_block_macs"] == []
    assert settings["tun"]["txqueuelen"] == 2000
    assert settings["singbox"]["version"] == "1.13.20"
    assert tun_inbound["interface_name"] == "opkgtun0"
    assert config["dns"]["cache_capacity"] > 512
    assert "clash_api" in config["experimental"]
    assert "rule_set" in config["route"]
    assert proxy["type"] == "urltest"
    assert proxy["interval"] == "30m"
    assert proxy["idle_timeout"] == "1h"
    assert geosite_rule["outbound"] == "proxy"
    assert {"hysteria2", "tuic", "direct"}.issubset(outbound_tags)


def test_default_template_has_inline_youtube_tv_fallback_before_quic_reject() -> None:
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    rules = config["route"]["rules"]
    youtube_index = next(
        i
        for i, rule in enumerate(rules)
        if ".googlevideo.com" in rule.get("domain_suffix", [])
    )
    quic_reject_index = next(
        i
        for i, rule in enumerate(rules)
        if rule.get("network") == "udp"
        and rule.get("port") == 443
        and rule.get("action") == "reject"
    )
    youtube_rule = rules[youtube_index]

    assert youtube_index < quic_reject_index
    assert youtube_rule["outbound"] == "proxy"
    assert "youtubei.googleapis.com" in youtube_rule["domain"]
    assert ".ytimg.com" in youtube_rule["domain_suffix"]
    assert ".ggpht.com" in youtube_rule["domain_suffix"]


def test_help_documents_download_fallbacks() -> None:
    result = subprocess.run(
        ["sh", str(SCRIPT), "--help"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "SINGBOX_URL" in result.stdout
    assert "install-config" in result.stdout
    assert "SINGBOX_PACKAGE" in result.stdout
    assert "SINGBOX_MIRROR_BASE" in result.stdout
    assert "SINGBOX_DOWNLOAD_MAX_TIME" in result.stdout
    assert "KEEN_SINGBOX_PROFILE" in result.stdout


def test_format_bytes_for_status() -> None:
    result = subprocess.run(
        ["sh", str(SCRIPT), "__test-format-bytes", "2048"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "2.00 KiB"


def test_wrapper_log_rotates_at_configured_limit(tmp_path: Path) -> None:
    log_path = tmp_path / "keen-singbox.log"
    log_path.write_text("x" * 32, encoding="utf-8")
    result = run_script(
        tmp_path,
        "__test-log",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_LOG=str(log_path),
        KEEN_SINGBOX_LOG_MAX_BYTES="16",
        LOG_LEVEL="error",
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "keen-singbox.log.1").read_text() == "x" * 32
    assert "test" in log_path.read_text()


def test_firewall_apply_adds_skeen_style_tun_rules(tmp_path: Path) -> None:
    iptables = make_iptables(tmp_path, check_status=1)
    iptables_log = tmp_path / "iptables.log"

    result = run_script(
        tmp_path,
        "__test-firewall-apply",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IPTABLES=str(iptables),
        IPTABLES_LOG=str(iptables_log),
    )

    assert result.returncode == 0, result.stderr
    logged = iptables_log.read_text(encoding="utf-8")
    assert "-t filter -N keen_singbox_tun" in logged
    assert "-t filter -C INPUT -i opkgtun0 -j keen_singbox_tun" in logged
    assert "-t filter -A INPUT -i opkgtun0 -j keen_singbox_tun" in logged
    assert "-t filter -A FORWARD -i opkgtun0 -j keen_singbox_tun" in logged
    assert "-t filter -A FORWARD -o opkgtun0 -j keen_singbox_tun" in logged
    assert "-t filter -A keen_singbox_tun -i opkgtun0 -j ACCEPT" in logged
    assert "-t filter -A keen_singbox_tun -o opkgtun0 -j ACCEPT" in logged
    assert "-t nat -A POSTROUTING -o opkgtun0 -j keen_singbox_nat" in logged
    assert "-t nat -A keen_singbox_nat -o opkgtun0 -j MASQUERADE" in logged
    assert not any(
        " -A " in line and "--comment" in line for line in logged.splitlines()
    )


def test_firewall_apply_is_idempotent_when_rules_exist(tmp_path: Path) -> None:
    iptables = make_iptables(tmp_path, check_status=0)
    iptables_log = tmp_path / "iptables.log"

    result = run_script(
        tmp_path,
        "__test-firewall-apply",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IPTABLES=str(iptables),
        IPTABLES_LOG=str(iptables_log),
    )

    assert result.returncode == 0, result.stderr
    logged = iptables_log.read_text(encoding="utf-8")
    assert "-t filter -C INPUT -i opkgtun0 -j keen_singbox_tun" in logged
    assert "-t filter -A INPUT -i opkgtun0 -j keen_singbox_tun" not in logged
    assert "-t filter -A FORWARD -i opkgtun0 -j keen_singbox_tun" not in logged
    assert "-t filter -A FORWARD -o opkgtun0 -j keen_singbox_tun" not in logged
    assert "-t nat -A POSTROUTING" not in logged


def test_firewall_remove_only_removes_own_tun_rules(tmp_path: Path) -> None:
    iptables = make_iptables(tmp_path)
    iptables_log = tmp_path / "iptables.log"

    result = run_script(
        tmp_path,
        "__test-firewall-remove",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IPTABLES=str(iptables),
        IPTABLES_LOG=str(iptables_log),
    )

    assert result.returncode == 0, result.stderr
    logged = iptables_log.read_text(encoding="utf-8")
    assert (
        "-t nat -D POSTROUTING -o opkgtun0 -j MASQUERADE "
        "-m comment --comment keen_singbox_tun"
    ) in logged
    assert "-t filter -D INPUT -i opkgtun0 -j keen_singbox_tun" in logged
    assert "-t filter -D FORWARD -i opkgtun0 -j keen_singbox_tun" in logged
    assert "-t filter -D FORWARD -o opkgtun0 -j keen_singbox_tun" in logged
    assert "-t filter -F keen_singbox_tun" in logged
    assert "-t filter -X keen_singbox_tun" in logged
    assert "-t nat -D POSTROUTING -o opkgtun0 -j keen_singbox_nat" in logged
    assert "-t nat -F keen_singbox_nat" in logged
    assert "-t nat -X keen_singbox_nat" in logged
    assert "skeen_tun" not in logged


def test_firewall_status_reports_applied_or_missing(tmp_path: Path) -> None:
    iptables = make_iptables(tmp_path, check_status=0)
    iptables_log = tmp_path / "iptables-applied.log"

    applied = run_script(
        tmp_path,
        "__test-firewall-status",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IPTABLES=str(iptables),
        IPTABLES_LOG=str(iptables_log),
    )

    iptables = make_iptables(tmp_path, check_status=1)
    iptables_log = tmp_path / "iptables-missing.log"
    missing = run_script(
        tmp_path,
        "__test-firewall-status",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IPTABLES=str(iptables),
        IPTABLES_LOG=str(iptables_log),
    )

    assert applied.returncode == 0, applied.stderr
    assert applied.stdout.strip() == "applied"
    assert missing.returncode == 0, missing.stderr
    assert missing.stdout.strip() == "missing"


def test_ipv6_client_block_uses_owned_chain_and_configured_mac(tmp_path: Path) -> None:
    settings = json.loads(DEFAULT_SETTINGS.read_text(encoding="utf-8"))
    settings["firewall"]["ipv6_block_macs"] = ["02:00:00:00:00:01"]
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings), encoding="utf-8")
    ip6tables = make_ip6tables(tmp_path, check_status=1)
    ip6tables_log = tmp_path / "ip6tables.log"

    result = run_script(
        tmp_path,
        "__test-ipv6-block-apply",
        KEEN_SINGBOX_SETTINGS=str(settings_path),
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IP6TABLES=str(ip6tables),
        IP6TABLES_LOG=str(ip6tables_log),
    )

    assert result.returncode == 0, result.stderr
    logged = ip6tables_log.read_text(encoding="utf-8")
    assert "-t filter -N keen_singbox_ipv6" in logged
    assert "-t filter -A FORWARD -j keen_singbox_ipv6" in logged
    assert "-t filter -F keen_singbox_ipv6" in logged
    assert (
        "-t filter -A keen_singbox_ipv6 -m mac "
        "--mac-source 02:00:00:00:00:01 -j REJECT"
    ) in logged
    assert "IPv6 is blocked for 1 configured client(s)" in result.stdout


def test_ipv6_client_block_status_and_remove(tmp_path: Path) -> None:
    settings = json.loads(DEFAULT_SETTINGS.read_text(encoding="utf-8"))
    settings["firewall"]["ipv6_block_macs"] = ["02:00:00:00:00:01"]
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings), encoding="utf-8")
    ip6tables = make_ip6tables(tmp_path, check_status=0)
    ip6tables_log = tmp_path / "ip6tables.log"
    env = {
        "KEEN_SINGBOX_SETTINGS": str(settings_path),
        "KEEN_SINGBOX_DRY_RUN": "0",
        "KEEN_SINGBOX_IP6TABLES": str(ip6tables),
        "IP6TABLES_LOG": str(ip6tables_log),
    }

    status = run_script(tmp_path, "__test-ipv6-block-status", **env)
    remove = run_script(tmp_path, "__test-ipv6-block-remove", **env)

    assert status.returncode == 0, status.stderr
    assert status.stdout.strip() == "applied (1 client(s))"
    assert remove.returncode == 0, remove.stderr
    logged = ip6tables_log.read_text(encoding="utf-8")
    assert "-t filter -D FORWARD -j keen_singbox_ipv6" in logged
    assert "-t filter -F keen_singbox_ipv6" in logged
    assert "-t filter -X keen_singbox_ipv6" in logged


def test_is_running_accepts_live_pid_from_pidfile(tmp_path: Path) -> None:
    pid_file = tmp_path / "keen-singbox.pid"
    proc = subprocess.Popen(["sleep", "20"])
    try:
        pid_file.write_text(str(proc.pid), encoding="utf-8")
        result = run_script(
            tmp_path,
            "status",
            KEEN_SINGBOX_PID_FILE=str(pid_file),
            KEEN_SINGBOX_DRY_RUN="0",
            KEEN_SINGBOX_PID_STRICT="0",
            KEEN_SINGBOX_STATUS_SAMPLE_SECONDS="0",
        )
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    assert result.returncode == 0, result.stderr
    assert "Running: yes" in result.stdout


def test_is_running_rejects_dead_or_invalid_pidfile(tmp_path: Path) -> None:
    pid_file = tmp_path / "keen-singbox.pid"
    pid_file.write_text("999999", encoding="utf-8")
    dead = run_script(
        tmp_path,
        "status",
        KEEN_SINGBOX_PID_FILE=str(pid_file),
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_STATUS_SAMPLE_SECONDS="0",
    )
    pid_file.write_text("not-a-pid", encoding="utf-8")
    invalid = run_script(
        tmp_path,
        "status",
        KEEN_SINGBOX_PID_FILE=str(pid_file),
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_STATUS_SAMPLE_SECONDS="0",
    )

    assert dead.returncode == 0, dead.stderr
    assert invalid.returncode == 0, invalid.stderr
    assert "Running: no" in dead.stdout
    assert "Running: no" in invalid.stdout


def test_is_running_rejects_unrelated_live_pid_in_strict_mode(tmp_path: Path) -> None:
    pid_file = tmp_path / "keen-singbox.pid"
    proc = subprocess.Popen(["sleep", "20"])
    try:
        pid_file.write_text(str(proc.pid), encoding="utf-8")
        result = run_script(
            tmp_path,
            "status",
            KEEN_SINGBOX_PID_FILE=str(pid_file),
            KEEN_SINGBOX_DRY_RUN="0",
            KEEN_SINGBOX_STATUS_SAMPLE_SECONDS="0",
        )
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    assert result.returncode == 0, result.stderr
    assert "Running: no" in result.stdout


def test_service_lock_rejects_live_owner_and_cleans_up(tmp_path: Path) -> None:
    lock_dir = tmp_path / "service.lock"
    lock_dir.mkdir()
    (lock_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")
    blocked = run_script(
        tmp_path,
        "__test-lock",
        KEEN_SINGBOX_LOCK_DIR=str(lock_dir),
        KEEN_SINGBOX_DRY_RUN="0",
    )
    assert blocked.returncode == 1
    assert "already running" in blocked.stderr

    (lock_dir / "pid").write_text("999999", encoding="utf-8")
    recovered = run_script(
        tmp_path,
        "__test-lock",
        KEEN_SINGBOX_LOCK_DIR=str(lock_dir),
        KEEN_SINGBOX_DRY_RUN="0",
    )
    assert recovered.returncode == 0, recovered.stderr
    assert not lock_dir.exists()


def test_write_runner_uses_runtime_script_with_direct_core_exec(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    runner = runtime_dir / "runner.sh"
    result = run_script(
        tmp_path,
        "__test-write-runner",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_RUNTIME_DIR=str(runtime_dir),
        KEEN_SINGBOX_RUNNER=str(runner),
        KEEN_SINGBOX_CORE="/opt/bin/keen-singbox-core",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(runner)
    assert runner.exists()
    assert os.access(runner, os.X_OK)
    content = runner.read_text(encoding="utf-8")
    assert content.startswith("#!/bin/sh\n")
    assert "exec '/opt/bin/keen-singbox-core' run" in content
    configured_work_dir = json.loads(SETTINGS.read_text())["singbox"]["work_dir"]
    configured_config = json.loads(SETTINGS.read_text())["singbox"]["config"]
    assert f"-D '{configured_work_dir}'" in content
    assert f"-c '{configured_config}'" in content
    assert f">>'{runtime_dir / 'sing-box.log'}' 2>&1" in content


def test_txqueuelen_is_applied_only_when_configured(tmp_path: Path) -> None:
    ip = make_ip(tmp_path)
    ndmc = make_ndmc(tmp_path)
    ip_log = tmp_path / "ip.log"
    ndmc_log = tmp_path / "ndmc.log"
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    settings["tun"]["txqueuelen"] = 1000
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings), encoding="utf-8")

    result = run_script(
        tmp_path,
        "__test-link-up",
        KEEN_SINGBOX_SETTINGS=str(settings_path),
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_NDMC=str(ndmc),
        KEEN_SINGBOX_IP=str(ip),
        IP_LOG=str(ip_log),
        NDMC_LOG=str(ndmc_log),
        KEEN_SINGBOX_TEST_INTERFACE_DATA="""
Interface, name = "OpkgTun0":
    description: SKeen0
    address: 172.19.0.1
""",
        KEEN_SINGBOX_TEST_POLICY_DATA="""
Policy, name = "Policy0":
    description: SKeen
    table4: 4096
""",
    )

    assert result.returncode == 0, result.stderr
    logged = ip_log.read_text(encoding="utf-8")
    assert "link set dev opkgtun0 up" in logged
    assert "link set dev opkgtun0 txqueuelen 1000" in logged


def test_set_txqueuelen_updates_settings_and_applies_link_queue(tmp_path: Path) -> None:
    ip = make_ip(tmp_path)
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    ip_log = tmp_path / "ip.log"

    result = run_script(
        tmp_path,
        "set-txqueuelen",
        KEEN_SINGBOX_SETTINGS=str(settings_path),
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IP=str(ip),
        IP_LOG=str(ip_log),
    )

    assert result.returncode == 1
    assert "txqueuelen value must be numeric" in result.stderr

    result = subprocess.run(
        ["sh", str(SCRIPT), "set-txqueuelen", "2000"],
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "KEEN_SINGBOX_SETTINGS": str(settings_path),
            "KEEN_SINGBOX_JSONFILTER": str(make_jsonfilter(tmp_path) / "jsonfilter"),
            "KEEN_SINGBOX_DRY_RUN": "0",
            "KEEN_SINGBOX_IP": str(ip),
            "IP_LOG": str(ip_log),
        },
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (
        json.loads(settings_path.read_text(encoding="utf-8"))["tun"]["txqueuelen"]
        == 2000
    )
    assert list(tmp_path.glob("settings.json.bak.*"))
    assert "link set dev opkgtun0 txqueuelen 2000" in ip_log.read_text(encoding="utf-8")


def test_invalid_txqueuelen_is_rejected(tmp_path: Path) -> None:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    settings["tun"]["txqueuelen"] = "fast"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings), encoding="utf-8")

    result = run_script(
        tmp_path,
        "validate",
        KEEN_SINGBOX_SETTINGS=str(settings_path),
        KEEN_SINGBOX_CORE="/bin/true",
        KEEN_SINGBOX_CONFIG=str(CONFIG),
    )

    assert result.returncode == 1
    assert "tun.txqueuelen must be numeric" in result.stderr


def test_clean_runtime_removes_only_tmp_cache_files(tmp_path: Path) -> None:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    cache_path = Path("/tmp") / f"keen-singbox-test-{tmp_path.name}.db"
    config["experimental"]["cache_file"]["path"] = str(cache_path)
    config_path = tmp_path / "config.json"
    settings["singbox"]["config"] = str(config_path)
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings), encoding="utf-8")
    config_path.write_text(json.dumps(config), encoding="utf-8")
    try:
        for path in (cache_path, Path(f"{cache_path}-shm"), Path(f"{cache_path}-wal")):
            path.write_text("cache", encoding="utf-8")

        result = run_script(
            tmp_path,
            "clean-runtime",
            KEEN_SINGBOX_SETTINGS=str(settings_path),
        )
    finally:
        for path in (cache_path, Path(f"{cache_path}-shm"), Path(f"{cache_path}-wal")):
            path.unlink(missing_ok=True)

    assert result.returncode == 0, result.stderr
    assert not cache_path.exists()
    assert not Path(f"{cache_path}-shm").exists()
    assert not Path(f"{cache_path}-wal").exists()


def test_clean_runtime_refuses_non_tmp_cache_file(tmp_path: Path) -> None:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    cache_path = ROOT / "cache.db"
    config["experimental"]["cache_file"]["path"] = str(cache_path)
    config_path = tmp_path / "config.json"
    settings["singbox"]["config"] = str(config_path)
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings), encoding="utf-8")
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = run_script(
        tmp_path,
        "clean-runtime",
        KEEN_SINGBOX_SETTINGS=str(settings_path),
    )

    assert result.returncode == 1
    assert "Refusing to remove non-runtime cache file" in result.stderr


def test_firewall_hook_install_is_idempotent_and_status_reports_it(
    tmp_path: Path,
) -> None:
    iptables = make_iptables(tmp_path, check_status=0)
    netfilter_dir = tmp_path / "netfilter.d"
    tmp_dir = tmp_path / "runtime"

    first = run_script(
        tmp_path,
        "__test-firewall-hook-install",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IPTABLES=str(iptables),
        KEEN_SINGBOX_NETFILTER_DIR=str(netfilter_dir),
        KEEN_SINGBOX_TMP_DIR=str(tmp_dir),
        IPTABLES_LOG=str(tmp_path / "iptables.log"),
    )
    hook = netfilter_dir / "keen-singbox-firewall.sh"
    first_mtime = hook.stat().st_mtime_ns
    second = run_script(
        tmp_path,
        "__test-firewall-hook-install",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IPTABLES=str(iptables),
        KEEN_SINGBOX_NETFILTER_DIR=str(netfilter_dir),
        KEEN_SINGBOX_TMP_DIR=str(tmp_dir),
        IPTABLES_LOG=str(tmp_path / "iptables.log"),
    )
    status = run_script(
        tmp_path,
        "__test-firewall-hook-status",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IPTABLES=str(iptables),
        KEEN_SINGBOX_NETFILTER_DIR=str(netfilter_dir),
        IPTABLES_LOG=str(tmp_path / "iptables.log"),
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert status.returncode == 0, status.stderr
    assert hook.exists()
    assert os.access(hook, os.X_OK)
    assert "__hook-firewall" in hook.read_text(encoding="utf-8")
    assert "ip6tables:filter" in hook.read_text(encoding="utf-8")
    assert hook.stat().st_mtime_ns == first_mtime
    assert status.stdout.strip() == "installed"


def test_firewall_hook_remove_deletes_installed_hook(tmp_path: Path) -> None:
    iptables = make_iptables(tmp_path, check_status=0)
    netfilter_dir = tmp_path / "netfilter.d"
    tmp_dir = tmp_path / "runtime"

    install = run_script(
        tmp_path,
        "__test-firewall-hook-install",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IPTABLES=str(iptables),
        KEEN_SINGBOX_NETFILTER_DIR=str(netfilter_dir),
        KEEN_SINGBOX_TMP_DIR=str(tmp_dir),
        IPTABLES_LOG=str(tmp_path / "iptables.log"),
    )
    remove = run_script(
        tmp_path,
        "__test-firewall-hook-remove",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_NETFILTER_DIR=str(netfilter_dir),
    )
    status = run_script(
        tmp_path,
        "__test-firewall-hook-status",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_NETFILTER_DIR=str(netfilter_dir),
        IPTABLES_LOG=str(tmp_path / "iptables.log"),
    )

    assert install.returncode == 0, install.stderr
    assert remove.returncode == 0, remove.stderr
    assert status.returncode == 0, status.stderr
    assert not (netfilter_dir / "keen-singbox-firewall.sh").exists()
    assert status.stdout.strip() == "missing"


def test_firewall_hook_entrypoint_reapplies_tun_rules(tmp_path: Path) -> None:
    iptables = make_iptables(tmp_path, check_status=1)
    iptables_log = tmp_path / "iptables.log"

    result = run_script(
        tmp_path,
        "__hook-firewall",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IPTABLES=str(iptables),
        IPTABLES_LOG=str(iptables_log),
    )

    assert result.returncode == 0, result.stderr
    logged = iptables_log.read_text(encoding="utf-8")
    assert "-t filter -A INPUT -i opkgtun0 -j keen_singbox_tun" in logged
    assert "-t filter -A FORWARD -i opkgtun0 -j keen_singbox_tun" in logged
    assert "-t filter -A FORWARD -o opkgtun0 -j keen_singbox_tun" in logged
    assert "-t nat -A POSTROUTING -o opkgtun0 -j keen_singbox_nat" in logged
    assert "-t nat -A keen_singbox_nat -o opkgtun0 -j MASQUERADE" in logged


def test_policy_table_from_plain_ndmc_policy(tmp_path: Path) -> None:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    settings["policy"]["name"] = "KeenSingBox"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings), encoding="utf-8")

    result = run_script(
        tmp_path,
        "__test-policy-table",
        KEEN_SINGBOX_SETTINGS=str(settings_path),
        KEEN_SINGBOX_TEST_POLICY_DATA="""
Policy, name = "Policy0":
    description: Other
    mark: 0x11
    table4: 17
Policy, name = "Policy1":
    description: KeenSingBox
    mark: 0x22
    table4: 34
""",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "34"


def test_policy_table_from_inline_description_ndmc_policy(tmp_path: Path) -> None:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    settings["policy"]["name"] = "SKeen"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings), encoding="utf-8")

    result = run_script(
        tmp_path,
        "__test-policy-table",
        KEEN_SINGBOX_SETTINGS=str(settings_path),
        KEEN_SINGBOX_TEST_POLICY_DATA="""
           policy, name = Policy0, description = SKeen:
                 mark: ffffaaa
               table4: 4096
""",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "4096"


def test_policy_table_from_mark_ip_rule_fallback(tmp_path: Path) -> None:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    settings["policy"]["name"] = "KeenSingBox"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings), encoding="utf-8")

    result = run_script(
        tmp_path,
        "__test-policy-table",
        KEEN_SINGBOX_SETTINGS=str(settings_path),
        KEEN_SINGBOX_TEST_POLICY_DATA="""
Policy, name = "Policy1":
    description: KeenSingBox
    mark: 0x25
""",
        KEEN_SINGBOX_TEST_IP_RULE_DATA="""
100: from all fwmark 0x25 lookup 37
32766: from all lookup main
""",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "37"


def test_policy_route_repair_flushes_all_default_routes(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    ip = bin_dir / "ip"
    state = tmp_path / "routes.txt"
    ip_log = tmp_path / "ip.log"
    state.write_text(
        "\n".join(
            [
                "default via 172.19.0.1 dev opkgtun0 metric 1000",
                "default dev opkgtun0 scope link metric 10",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ip.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$IP_LOG"
if [ "$*" = "route show table 4096" ]; then
  cat "$IP_STATE"
  exit 0
fi
if [ "$*" = "route del default table 4096" ]; then
  [ -s "$IP_STATE" ] || exit 2
  sed -n '2,$p' "$IP_STATE" > "${IP_STATE}.tmp"
  mv "${IP_STATE}.tmp" "$IP_STATE"
  exit 0
fi
if [ "$*" = "route add default dev opkgtun0 table 4096 metric 10" ]; then
  echo "default dev opkgtun0 scope link metric 10" > "$IP_STATE"
  exit 0
fi
exit 0
""",
        encoding="utf-8",
    )
    ip.chmod(0o755)

    result = run_script(
        tmp_path,
        "__test-policy-route",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IP=str(ip),
        IP_LOG=str(ip_log),
        IP_STATE=str(state),
        KEEN_SINGBOX_TEST_POLICY_DATA="""
Policy, name = "Policy0":
    description: SKeen
    table4: 4096
""",
    )

    assert result.returncode == 0, result.stderr
    logged = ip_log.read_text(encoding="utf-8")
    assert logged.count("route del default table 4096") == 2
    assert "route add default dev opkgtun0 table 4096 metric 10" in logged


def test_policy_route_remove_keeps_native_policy_default(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    ip = bin_dir / "ip"
    state = tmp_path / "routes.txt"
    ip_log = tmp_path / "ip.log"
    state.write_text(
        "\n".join(
            [
                "default via 172.19.0.1 dev opkgtun0 metric 1000",
                "default dev ppp0 scope link metric 1000",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ip.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$IP_LOG"
if [ "$*" = "route show table 4096" ]; then
  cat "$IP_STATE"
  exit 0
fi
if [ "$*" = "route del default table 4096" ]; then
  exit 2
fi
if [ "$*" = "route del default dev opkgtun0 table 4096" ]; then
  exit 2
fi
if [ "$*" = "route del default via 172.19.0.1 dev opkgtun0 table 4096" ]; then
  grep -v 'dev opkgtun0' "$IP_STATE" > "${IP_STATE}.tmp"
  mv "${IP_STATE}.tmp" "$IP_STATE"
  exit 0
fi
exit 0
""",
        encoding="utf-8",
    )
    ip.chmod(0o755)

    result = run_script(
        tmp_path,
        "__test-policy-route-remove",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IP=str(ip),
        IP_LOG=str(ip_log),
        IP_STATE=str(state),
        KEEN_SINGBOX_TEST_POLICY_DATA="""
Policy, name = "Policy0":
    description: SKeen
    table4: 4096
""",
    )

    assert result.returncode == 0, result.stderr
    logged = ip_log.read_text(encoding="utf-8")
    assert "route del default via 172.19.0.1 dev opkgtun0 table 4096" in logged
    assert (
        state.read_text(encoding="utf-8") == "default dev ppp0 scope link metric 1000\n"
    )


def test_status_reports_invalid_policy_route_gateway(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    ip = bin_dir / "ip"
    ip_log = tmp_path / "ip.log"
    ip.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$IP_LOG"
case "$*" in
  "route show table 4096")
    echo "default via 172.19.0.1 dev opkgtun0 metric 1000"
    ;;
  "link show dev opkgtun0")
    echo "46: opkgtun0: <POINTOPOINT,MULTICAST,NOARP,UP,LOWER_UP> mtu 1400"
    ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    ip.chmod(0o755)

    result = run_script(
        tmp_path,
        "status",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IP=str(ip),
        IP_LOG=str(ip_log),
        KEEN_SINGBOX_STATUS_SAMPLE_SECONDS="0",
        KEEN_SINGBOX_TEST_POLICY_DATA="""
Policy, name = "Policy0":
    description: SKeen
    table4: 4096
""",
    )

    assert result.returncode == 0, result.stderr
    assert (
        "Default route problem: invalid gateway: policy table routes via its own "
        "TUN address 172.19.0.1"
    ) in result.stdout


def test_doctor_reports_invalid_policy_route_with_fix(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    ip = bin_dir / "ip"
    ip_log = tmp_path / "ip.log"
    ip.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$IP_LOG"
case "$*" in
  "route show table 4096")
    echo "default via 172.19.0.1 dev opkgtun0 metric 1000"
    ;;
  "link show dev opkgtun0")
    echo "46: opkgtun0: <POINTOPOINT,MULTICAST,NOARP,UP,LOWER_UP> mtu 1400 qlen 2000"
    ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    ip.chmod(0o755)

    result = run_script(
        tmp_path,
        "doctor",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IP=str(ip),
        IP_LOG=str(ip_log),
        KEEN_SINGBOX_TEST_POLICY_DATA="""
Policy, name = "Policy0":
    description: SKeen
    table4: 4096
""",
    )

    assert result.returncode == 0, result.stderr
    assert (
        "invalid gateway: policy table routes via its own TUN address 172.19.0.1"
        in result.stdout
    )
    assert "Fix: keen-singbox restart" in result.stdout


def test_doctor_reports_remote_rule_set_cache_status(tmp_path: Path) -> None:
    ip = tmp_path / "bin" / "ip"
    ip.parent.mkdir(exist_ok=True)
    ip.write_text(
        """#!/bin/sh
case "$*" in
  "route show table 4096")
    echo "default dev opkgtun0 scope link metric 10"
    ;;
  "link show dev opkgtun0")
    echo "46: opkgtun0: <POINTOPOINT,MULTICAST,NOARP,UP,LOWER_UP> mtu 1400 qlen 2000"
    ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    ip.chmod(0o755)
    iptables = make_iptables(tmp_path, check_status=0)
    core = make_singbox_core(tmp_path)
    cache_path = tmp_path / "cache.db"
    cache_path.write_bytes(b"cache")
    log_path = tmp_path / "sing-box.log"
    log_path.write_text("remote rule-set download complete\n", encoding="utf-8")

    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config["experimental"]["cache_file"]["path"] = str(cache_path)
    config["log"]["output"] = str(log_path)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    settings = json.loads(DEFAULT_SETTINGS.read_text(encoding="utf-8"))
    settings["singbox"]["config"] = str(config_path)
    settings["singbox"]["bin"] = str(core)
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings), encoding="utf-8")

    pid_file = tmp_path / "keen-singbox.pid"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    result = run_script(
        tmp_path,
        "doctor",
        KEEN_SINGBOX_SETTINGS=str(settings_path),
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IP=str(ip),
        KEEN_SINGBOX_IPTABLES=str(iptables),
        KEEN_SINGBOX_PID_FILE=str(pid_file),
        IPTABLES_LOG=str(tmp_path / "iptables.log"),
        KEEN_SINGBOX_TEST_INTERFACE_DATA="""
Interface, name = "OpkgTun0":
    description: SKeen0
    address: 172.19.0.1
""",
        KEEN_SINGBOX_TEST_POLICY_DATA="""
Policy, name = "Policy0":
    description: SKeen
    table4: 4096
""",
    )

    assert result.returncode == 0, result.stderr
    assert "Remote rule sets configured:" in result.stdout
    assert f"Remote rule-set cache exists: {cache_path}" in result.stdout
    assert "No recent remote rule-set errors in sing-box log" in result.stdout


def test_doctor_does_not_report_empty_policy_table_as_found(tmp_path: Path) -> None:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    settings["policy"]["name"] = "KeenSingBox"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings), encoding="utf-8")

    result = run_script(
        tmp_path,
        "doctor",
        KEEN_SINGBOX_SETTINGS=str(settings_path),
        KEEN_SINGBOX_CORE="/bin/sh",
        KEEN_SINGBOX_CONFIG=str(CONFIG),
        KEEN_SINGBOX_TEST_POLICY_DATA="""
Policy, name = "Policy1":
    description: Other
    mark: 0x25
""",
        KEEN_SINGBOX_TEST_IP_RULE_DATA="32766: from all lookup main",
    )

    assert result.returncode == 0, result.stderr
    assert "policy table not found for 'KeenSingBox'" in result.stdout
    assert "policy table found" not in result.stdout


def test_iface_by_description_from_plain_ndmc_interface(tmp_path: Path) -> None:
    result = run_script(
        tmp_path,
        "__test-iface-by-name",
        KEEN_SINGBOX_TEST_INTERFACE_DATA="""
Interface, name = "OpkgTun0":
    description: Other
    address: 172.19.0.5
Interface, name = "OpkgTun1":
    description: SKeen0
    address: 172.19.0.1
""",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OpkgTun1"


def test_iface_by_description_from_inline_ndmc_interface(tmp_path: Path) -> None:
    result = run_script(
        tmp_path,
        "__test-iface-by-name",
        KEEN_SINGBOX_TEST_INTERFACE_DATA="""
           interface, name = OpkgTun0, description = Other:
           interface, name = OpkgTun1, description = SKeen0:
""",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OpkgTun1"


def test_opkgtun_binding_rejects_foreign_configured_interface(
    tmp_path: Path,
) -> None:
    result = run_script(
        tmp_path,
        "__test-opkgtun-binding",
        KEEN_SINGBOX_TEST_INTERFACE_DATA="""
           interface, name = OpkgTun0, description = OtherTun:
""",
    )

    assert result.returncode == 1
    assert "OpkgTun0 already exists with description 'OtherTun'" in result.stderr


def test_expected_opkgtun_comes_from_configured_linux_iface(tmp_path: Path) -> None:
    result = run_script(
        tmp_path,
        "__test-expected-opkgtun",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OpkgTun0"


def make_stateful_iptables(tmp_path: Path) -> Path:
    iptables = tmp_path / "iptables-stateful"
    implementation = tmp_path / "iptables-stateful.py"
    implementation.write_text(
        """
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
if '--comment' in args and os.environ.get('NO_COMMENT') == '1':
    print('iptables: No chain/target/match by that name.', file=sys.stderr)
    sys.exit(1)
if '-A' in args and 'MASQUERADE' in args and os.environ.get('NO_MASQUERADE') == '1':
    print('iptables: No chain/target/match by that name.', file=sys.stderr)
    sys.exit(1)
path = Path(os.environ['IPTABLES_STATE'])
state = json.loads(path.read_text()) if path.exists() else {
    'filter': {'INPUT': [], 'FORWARD': []}, 'nat': {'POSTROUTING': []}
}
table = state[args[args.index('-t') + 1]]
op_index = next(i for i, arg in enumerate(args) if arg in ('-N', '-A', '-C', '-D', '-F', '-X'))
op, chain, *rule = args[op_index:]
if op == '-N':
    if chain in table:
        sys.exit(1)
    table[chain] = []
elif chain not in table:
    sys.exit(1)
elif op == '-A':
    target = rule[rule.index('-j') + 1]
    if target not in ('ACCEPT', 'MASQUERADE') and target not in table:
        sys.exit(1)
    table[chain].append(rule)
elif op == '-C':
    sys.exit(0 if rule in table[chain] else 1)
elif op == '-D':
    if rule not in table[chain]:
        sys.exit(1)
    table[chain].remove(rule)
elif op == '-F':
    table[chain] = []
elif op == '-X':
    if table[chain] or any(chain in rule for rules in table.values() for rule in rules):
        sys.exit(1)
    del table[chain]
path.write_text(json.dumps(state))
""",
        encoding="utf-8",
    )
    iptables.write_text(
        "#!/bin/sh\n"
        f"exec {shlex.quote(sys.executable)} "
        f"{shlex.quote(str(implementation))} \"$@\"\n",
        encoding="utf-8",
    )
    iptables.chmod(0o755)
    return iptables


def test_firewall_without_comment_module_recovers_and_removes_only_owned_rules(
    tmp_path: Path,
) -> None:
    iptables = make_stateful_iptables(tmp_path)
    state_path = tmp_path / "iptables.json"
    original = {
        "filter": {"INPUT": [], "FORWARD": []},
        "nat": {"POSTROUTING": [["-o", "opkgtun0", "-j", "MASQUERADE"]]},
    }
    state_path.write_text(json.dumps(original))
    env = dict(
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IPTABLES=str(iptables),
        IPTABLES_STATE=str(state_path),
        NO_COMMENT="1",
    )
    for _ in range(2):
        applied = run_script(tmp_path, "__test-firewall-apply", **env)
        assert applied.returncode == 0, applied.stderr
    state = json.loads(state_path.read_text())
    assert len(state["nat"]["POSTROUTING"]) == 2
    assert len(state["nat"]["keen_singbox_nat"]) == 1
    assert (
        run_script(tmp_path, "__test-firewall-status", **env).stdout.strip()
        == "applied"
    )

    # Keep all jumps but simulate the router clearing a chain's contents.
    state["nat"]["keen_singbox_nat"] = []
    state_path.write_text(json.dumps(state))
    assert (
        run_script(tmp_path, "__test-firewall-status", **env).stdout.strip()
        == "missing"
    )
    repaired = run_script(tmp_path, "__hook-firewall", **env)
    assert repaired.returncode == 0, repaired.stderr
    assert (
        run_script(tmp_path, "__test-firewall-status", **env).stdout.strip()
        == "applied"
    )

    removed = run_script(tmp_path, "__test-firewall-remove", **env)
    assert removed.returncode == 0, removed.stderr
    assert json.loads(state_path.read_text()) == original


def test_firewall_migrates_legacy_tagged_nat_rule(tmp_path: Path) -> None:
    state_path = tmp_path / "iptables.json"
    unrelated = ["-o", "opkgtun0", "-j", "MASQUERADE"]
    legacy = unrelated + ["-m", "comment", "--comment", "keen_singbox_tun"]
    state_path.write_text(
        json.dumps(
            {
                "filter": {"INPUT": [], "FORWARD": []},
                "nat": {"POSTROUTING": [unrelated, legacy]},
            }
        )
    )
    result = run_script(
        tmp_path,
        "__test-firewall-apply",
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IPTABLES=str(make_stateful_iptables(tmp_path)),
        IPTABLES_STATE=str(state_path),
    )
    assert result.returncode == 0, result.stderr
    nat = json.loads(state_path.read_text())["nat"]
    assert nat["POSTROUTING"] == [
        unrelated,
        ["-o", "opkgtun0", "-j", "keen_singbox_nat"],
    ]
    assert nat["keen_singbox_nat"] == [["-o", "opkgtun0", "-j", "MASQUERADE"]]


@pytest.mark.parametrize("missing_masquerade", [False, True])
def test_start_completes_without_comment_but_reports_real_nat_failure(
    tmp_path: Path,
    missing_masquerade: bool,
) -> None:
    settings = json.loads(SETTINGS.read_text())
    settings["singbox"]["bin"] = str(make_singbox_core(tmp_path))
    settings["singbox"]["config"] = str(CONFIG)
    settings["runtime"]["dir"] = str(tmp_path / "runtime")
    settings["policy"]["table4"] = "4096"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings))
    routes = tmp_path / "routes"
    routes.write_text("default via 172.19.0.1 dev opkgtun0 metric 1000\n")
    ip = make_ip(tmp_path)
    ip.write_text("""#!/bin/sh
case "$*" in
  "link show dev opkgtun0") echo '46: opkgtun0: <UP,LOWER_UP> state UP' ;;
  "route show table 4096") cat "$IP_STATE" ;;
  "route del default table 4096") : > "$IP_STATE" ;;
  "route add default dev opkgtun0 table 4096 metric 10")
    echo 'default dev opkgtun0 scope link metric 10' > "$IP_STATE" ;;
esac
exit 0
""")
    pid_file = tmp_path / "pid"
    # A live, test-owned PID exercises start's repair of an already-running core.
    pid_file.write_text(str(os.getpid()))
    result = run_script(
        tmp_path,
        "start",
        KEEN_SINGBOX_SETTINGS=str(settings_path),
        KEEN_SINGBOX_DRY_RUN="0",
        KEEN_SINGBOX_IP=str(ip),
        IP_STATE=str(routes),
        KEEN_SINGBOX_PID_FILE=str(pid_file),
        KEEN_SINGBOX_PID_STRICT="0",
        KEEN_SINGBOX_NDMC=str(make_ndmc(tmp_path)),
        NDMC_LOG=str(tmp_path / "ndmc.log"),
        KEEN_SINGBOX_IPTABLES=str(make_stateful_iptables(tmp_path)),
        IPTABLES_STATE=str(tmp_path / "iptables.json"),
        NO_COMMENT="1",
        NO_MASQUERADE="1" if missing_masquerade else "0",
        KEEN_SINGBOX_NETFILTER_DIR=str(tmp_path / "netfilter.d"),
        KEEN_SINGBOX_TMP_DIR=str(tmp_path / "runtime" / "tmp"),
        KEEN_SINGBOX_TEST_INTERFACE_DATA="""Interface, name = "OpkgTun0":
    description: SKeen0
    address: 172.19.0.1
""",
    )
    assert (tmp_path / "netfilter.d" / "keen-singbox-firewall.sh").exists()
    if missing_masquerade:
        assert result.returncode == 1
        assert "Failed to add iptables nat rule: keen_singbox_nat" in result.stderr
        assert "Service startup completed" not in result.stdout
        assert "via 172.19.0.1" in routes.read_text()
    else:
        assert result.returncode == 0, result.stderr
        assert "Service startup completed" in result.stdout
        assert routes.read_text() == "default dev opkgtun0 scope link metric 10\n"


def test_init_dispatches_actions_and_preserves_start_failure_log(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "service bin"
    bin_dir.mkdir()
    cli = bin_dir / "keen-singbox"
    cli.write_text("""#!/bin/sh
echo "$*" >> "$INIT_CALLS"
echo 'boot failure detail' >&2
exit 7
""")
    cli.chmod(0o755)
    settings = json.loads(SETTINGS.read_text())
    settings["runtime"]["dir"] = str(tmp_path / "runtime dir")
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(settings))
    installed = run_script(
        tmp_path,
        "install-init",
        KEEN_SINGBOX_SETTINGS=str(settings_path),
        KEEN_SINGBOX_INIT_DIR=str(tmp_path / "init.d"),
        KEEN_SINGBOX_BIN_DIR=str(bin_dir),
    )
    assert installed.returncode == 0, installed.stderr
    init = tmp_path / "init.d" / "S99KeenSingBox"
    calls = tmp_path / "init-calls"
    for args in ([], ["start"], ["stop"], ["restart"], ["reload"], ["status"]):
        result = subprocess.run(
            [str(init), *args],
            env={**os.environ, "INIT_CALLS": str(calls)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 7
    assert calls.read_text().splitlines() == [
        "start --init",
        "start --init",
        "stop",
        "restart",
        "reload",
        "status",
    ]
    assert (tmp_path / "runtime dir" / "init.log").read_text().count(
        "boot failure detail"
    ) == 2
