#!/usr/bin/python3
"""Pinned Codex exec adapter for the disposable paired benchmark jobs.

Place launcher-config.json next to this file. Required keys are codex_path and
codex_sha256. Optional keys: codex_version, model (gpt-6-astra), reasoning_effort
(max), model_provider (my_codex), cpu_affinity (CPU IDs), python_hash_seed (0),
disabled_mcp_servers ([]), log_path (launcher-events.jsonl), job_id, codex_home,
and isolation. Isolation contains hidden_roots, read_only and writable lists;
bind entries are absolute paths or {source, target} mappings. Read-only files
are mounted last so an auth-file mapping remains read-only inside codex_home.

This executable replaces itself with Codex (or bwrap), preserving stdin,
stdout, stderr and the host process group. Direct mode also preserves the CLI
PID; isolation runs it inside bwrap's PID namespace. It does not supervise the
campaign or read auth files.
The network settings constrain benchmark inputs; workspace-write is not strict
holdout read isolation. Model/provider fields describe requested settings.

Config keys checked against the official Codex configuration reference and
codex-cli 0.167.0 exec/resume help on 2026-11-10:
https://developers.openai.com/codex/config-reference/
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib


MODEL = "gpt-6-astra"
EFFORT = "max"
PROVIDER = "my_codex"
THREAD_ENV = {name: "1" for name in (
    "OMP_NUM_THREADS", "OMP_THREAD_LIMIT", "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS", "RAYON_NUM_THREADS",
)}


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _overrides(config: dict) -> tuple[dict, dict[str, str]]:
    for key, expected in (("model", MODEL), ("reasoning_effort", EFFORT),
                          ("model_provider", PROVIDER)):
        if config.get(key, expected) != expected:
            raise ValueError(f"{key} differs from the paired benchmark setting")
    seed = config.get("python_hash_seed", 0)
    if type(seed) is not int or not 0 <= seed <= 4294967295:
        raise ValueError("python_hash_seed must be an integer from 0 through 4294967295")
    environment = {**THREAD_ENV, "PYTHONHASHSEED": str(seed)}
    overrides = {
        "model": MODEL, "model_reasoning_effort": EFFORT, "model_provider": PROVIDER,
        "sandbox_mode": "workspace-write", "approval_policy": "never",
        "sandbox_workspace_write.network_access": False,
        "web_search": "disabled", "features.apps": False,
        **{"shell_environment_policy.set." + key: value for key, value in environment.items()},
    }
    servers = config.get("disabled_mcp_servers", [])
    if not isinstance(servers, list) or any(not isinstance(name, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]+", name) for name in servers):
        raise ValueError("disabled_mcp_servers must be a list of simple MCP server IDs")
    overrides.update({f"mcp_servers.{name}.enabled": False for name in servers})
    return overrides, environment


def _command(binary: Path, original: list[str], overrides: dict) -> list[str]:
    if not original or original[0] != "exec":
        raise ValueError("launcher expects the campaign's exec or exec resume command")
    # Existing old/new drivers supply these flags themselves. Keep their bytes
    # and order, but do not permit a caller to negate the fixed benchmark setup.
    values = {"--model": MODEL, "-m": MODEL,
              "--sandbox": "workspace-write", "-s": "workspace-write"}
    forbidden = {"--dangerously-bypass-approvals-and-sandbox", "--yolo",
                 "--full-auto", "--approve-for-me", "--oss", "--local-provider"}
    index = 1
    while index < len(original):
        item = original[index]
        flag, equal, inline = item.partition("=")
        if flag in forbidden:
            raise ValueError("caller requested an incompatible sandbox or provider option")
        if flag in values or flag in {"-c", "--config"}:
            if equal:
                value = inline
            else:
                index += 1
                if index == len(original):
                    raise ValueError("caller option is missing its value")
                value = original[index]
            if flag in values and value != values[flag]:
                raise ValueError("caller option differs from the paired benchmark setting")
            if flag in {"-c", "--config"}:
                key, separator, raw = value.partition("=")
                key = key.strip()
                if not separator:
                    raise ValueError("caller config option is missing its value")
                protected = [name for name in overrides if name == key or name.startswith(key + ".")]
                if protected:
                    try:
                        parsed = tomllib.loads("value=" + raw)["value"]
                    except tomllib.TOMLDecodeError:
                        parsed = raw
                    if key not in overrides or parsed != overrides[key]:
                        raise ValueError("caller config differs from the paired benchmark setting")
        index += 1
    prefix = 2 if original[1:2] == ["resume"] else 1
    extra = [argument for key, value in overrides.items()
             for argument in ("-c", key + "=" + json.dumps(value))]
    return [str(binary), *original[:prefix], *extra, *original[prefix:]]


def _logged_argv(argv: list[str]) -> list[str]:
    """Do not write secret config values to the job's audit log."""
    safe = list(argv)
    for index, value in enumerate(safe):
        prefix = "--config=" if value.startswith("--config=") else ""
        key, separator, _ = value[len(prefix):].partition("=")
        if separator and re.search(r"(?:api[_-]?key|token|secret|password|authorization|headers)", key, re.I):
            safe[index] = prefix + key + "=<redacted>"
    return safe


def _isolated_command(command: list[str], config: dict) -> list[str]:
    isolation = config.get("isolation")
    if isolation is None:
        return command
    if not isinstance(isolation, dict):
        raise ValueError("isolation must be an object")

    def absolute(value):
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("isolation paths must be absolute without parent traversal")
        return str(path)

    result = ["/usr/bin/bwrap", "--ro-bind", "/", "/"]
    for root in isolation.get("hidden_roots", []):
        result += ["--tmpfs", absolute(root)]
    readonly_files = []
    for name, option in (("read_only", "--ro-bind"), ("writable", "--bind")):
        for entry in isolation.get(name, []):
            source, target = (entry, entry) if isinstance(entry, str) else (entry["source"], entry["target"])
            source, target = absolute(source), absolute(target)
            if not Path(source).exists():
                raise ValueError("isolation bind source does not exist: " + source)
            arguments = [option, source, target]
            if name == "read_only" and Path(source).is_file():
                readonly_files += arguments
            else:
                result += arguments
    result += readonly_files
    # Keep the host process group for campaign_runtime killpg. The PID
    # namespace/proc mount prevents /proc/<hostpid>/root bypassing hidden roots.
    return [*result, "--unshare-pid", "--proc", "/proc", "--dev", "/dev",
            "--die-with-parent", "--", *command]


def main() -> None:
    launcher = Path(__file__).absolute()
    config_path = launcher.with_name("launcher-config.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    binary = Path(config["codex_path"]).expanduser()
    if not binary.is_absolute():
        raise ValueError("codex_path must be absolute")
    binary = binary.resolve(strict=True)
    digest = _digest(binary)
    if binary.samefile(launcher) or digest == _digest(launcher):
        raise ValueError("codex_path resolves to a launcher, not the real CLI")
    if digest != config["codex_sha256"]:
        raise ValueError("Codex executable sha256 changed")
    if not os.access(binary, os.X_OK):
        raise ValueError("codex_path is not executable")
    overrides, fixed_env = _overrides(config)
    command = _command(binary, sys.argv[1:], overrides)
    affinity = config.get("cpu_affinity")
    if affinity is not None:
        if (not isinstance(affinity, list) or not affinity or
                any(type(cpu) is not int or cpu < 0 for cpu in affinity)):
            raise ValueError("cpu_affinity must contain nonnegative integer CPU IDs")
        os.sched_setaffinity(0, affinity)
        if os.sched_getaffinity(0) != set(affinity):
            raise ValueError("requested CPU affinity was not applied exactly")
    environment = {**os.environ, **fixed_env}
    if "codex_home" in config:
        codex_home = Path(config["codex_home"])
        if not codex_home.is_absolute() or not codex_home.is_dir():
            raise ValueError("codex_home must name an existing absolute directory")
        environment["CODEX_HOME"] = str(codex_home)
    execute = _isolated_command(command, config)
    version_result = subprocess.run([str(binary), "--version"], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, env=environment, timeout=10, check=True)
    version = version_result.stdout.strip()
    if not re.fullmatch(r"codex-cli [^\r\n]{1,120}", version):
        raise ValueError("real CLI did not report a Codex version")
    if config.get("codex_version", version) != version:
        raise ValueError("Codex version differs from launcher-config.json")
    log = Path(config.get("log_path", str(launcher.with_name("launcher-events.jsonl"))))
    if not log.is_absolute():
        log = launcher.parent / log
    event = {
        "event": "codex_exec", "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "job_id": config.get("job_id"), "pid": os.getpid(), "pgid": os.getpgrp(),
        "codex_path": str(binary), "codex_sha256": digest, "codex_version": version,
        "requested_model": MODEL, "requested_reasoning_effort": EFFORT,
        "requested_model_provider": PROVIDER, "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "fixed_environment": fixed_env, "argv": _logged_argv(command),
        "launcher_exec_argv": _logged_argv(execute), "codex_home": config.get("codex_home"),
    }
    with log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    # execve preserves the worker's process group and streams; old runtime
    # termination and recovery continue to own every process in that group.
    os.execve(execute[0], execute, environment)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"paired launcher: {exc}", file=sys.stderr)
        raise SystemExit(78)
