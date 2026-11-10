from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "agent_launcher.py"
FAKE_CLI = r'''#!/usr/bin/python3
import json, os, pathlib, sys, time
if sys.argv[1:] == ["--version"]:
    print("codex-cli 0.167.0-test")
    raise SystemExit(0)
payload = sys.stdin.buffer.read()
captured = {
    "argv": sys.argv[1:], "stdin_hex": payload.hex(), "pid": os.getpid(), "pgid": os.getpgrp(),
    "affinity": sorted(os.sched_getaffinity(0)),
    "environment": {key: os.environ.get(key) for key in (
        "PYTHONHASHSEED", "OMP_NUM_THREADS", "OMP_THREAD_LIMIT", "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
        "BLIS_NUM_THREADS", "RAYON_NUM_THREADS", "UNRELATED_SENTINEL", "CODEX_HOME")},
}
if "FAKE_PROBES" in os.environ:
    captured["probes"] = {}
    for name, path in json.loads(os.environ["FAKE_PROBES"]).items():
        try:
            content = pathlib.Path(path).read_text()
            captured["probes"][name] = {"readable": True, "content": content}
        except OSError:
            captured["probes"][name] = {"readable": False}
    captured["readonly_write_blocked"] = {}
    for path in json.loads(os.environ.get("FAKE_READONLY", "[]")):
        try:
            pathlib.Path(path).write_text("unexpected write")
            captured["readonly_write_blocked"][path] = False
        except OSError:
            captured["readonly_write_blocked"][path] = True
pathlib.Path(os.environ["FAKE_CAPTURE"]).write_text(json.dumps(captured))
sys.stdout.buffer.write(b'{"type":"thread.started","thread_id":"fake"}\n')
sys.stdout.buffer.write(b'{"type":"turn.completed","usage":{}}\n')
sys.stderr.write("fake stderr\n")
if os.environ.get("FAKE_HOLD"):
    time.sleep(30)
raise SystemExit(int(os.environ.get("FAKE_EXIT", "0")))
'''


class AgentLauncherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.launcher = self.root / "agent-launcher"
        shutil.copyfile(SOURCE, self.launcher)
        self.launcher.chmod(0o755)
        self.cli = self.root / "fake-codex"
        self.cli.write_text(FAKE_CLI)
        self.cli.chmod(0o755)
        self.capture = self.root / "capture.json"
        self.config = {
            "codex_path": str(self.cli),
            "codex_sha256": hashlib.sha256(self.cli.read_bytes()).hexdigest(),
            "codex_version": "codex-cli 0.167.0-test",
            "model": "gpt-6-astra", "reasoning_effort": "max", "model_provider": "my_codex",
            "cpu_affinity": [min(os.sched_getaffinity(0))], "python_hash_seed": 23,
            "job_id": "disposable-test", "disabled_mcp_servers": ["fixture-server"],
        }

    def launch(self, arguments, *, exit_code=0, extra_env=None):
        (self.root / "launcher-config.json").write_text(json.dumps(self.config))
        process = subprocess.Popen(
            [str(self.launcher), *arguments], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True,
            cwd=self.root / "workspace" if "isolation" in self.config else None,
            env={**os.environ, "FAKE_CAPTURE": str(self.capture), "FAKE_EXIT": str(exit_code),
                 "OMP_NUM_THREADS": "99", "PYTHONHASHSEED": "99", "UNRELATED_SENTINEL": "kept",
                 **(extra_env or {})})
        return process

    def invoke(self, arguments, *, exit_code=0, payload=b"synthetic prompt\n", extra_env=None):
        process = self.launch(arguments, exit_code=exit_code, extra_env=extra_env)
        stdout, stderr = process.communicate(payload, timeout=15)
        return process.pid, process.returncode, stdout, stderr

    @staticmethod
    def config_arguments(arguments):
        return {arguments[index + 1].split("=", 1)[0]: json.loads(arguments[index + 1].split("=", 1)[1])
                for index, item in enumerate(arguments[:-1]) if item == "-c"}

    def test_exec_preserves_streams_exit_environment_and_process_group(self):
        original = ["exec", "-C", "/tmp/work space", "--skip-git-repo-check",
                    "--sandbox", "workspace-write", "--json", "--output-schema", "/tmp/schema.json",
                    "-o", "/tmp/message.json", "--model", "gpt-6-astra", "--add-dir", "/tmp/campaign", "-"]
        payload = "字节保持\n".encode() + b"\x00tail"
        pid, code, stdout, stderr = self.invoke(original, exit_code=17, payload=payload)
        self.assertEqual(code, 17)
        self.assertEqual(stdout, b'{"type":"thread.started","thread_id":"fake"}\n'
                         b'{"type":"turn.completed","usage":{}}\n')
        self.assertEqual(stderr, b"fake stderr\n")
        captured = json.loads(self.capture.read_text())
        self.assertEqual(bytes.fromhex(captured["stdin_hex"]), payload)
        self.assertEqual((captured["pid"], captured["pgid"]), (pid, pid))
        self.assertEqual(captured["affinity"], self.config["cpu_affinity"])
        self.assertEqual(captured["environment"]["UNRELATED_SENTINEL"], "kept")
        self.assertEqual(captured["environment"]["PYTHONHASHSEED"], "23")
        for name, value in captured["environment"].items():
            if name not in {"UNRELATED_SENTINEL", "PYTHONHASHSEED", "CODEX_HOME"}:
                self.assertEqual(value, "1", name)
        extra_count = len(captured["argv"]) - len(original)
        self.assertEqual(captured["argv"][:1] + captured["argv"][1 + extra_count:], original)
        overrides = self.config_arguments(captured["argv"])
        for key, expected in {
            "model": "gpt-6-astra", "model_reasoning_effort": "max", "model_provider": "my_codex",
            "web_search": "disabled", "features.apps": False, "sandbox_mode": "workspace-write",
            "sandbox_workspace_write.network_access": False, "approval_policy": "never",
            "mcp_servers.fixture-server.enabled": False,
            "shell_environment_policy.set.PYTHONHASHSEED": "23",
            "shell_environment_policy.set.OMP_NUM_THREADS": "1",
        }.items():
            self.assertEqual(overrides[key], expected)
        log = json.loads((self.root / "launcher-events.jsonl").read_text())
        self.assertEqual(log["argv"], [str(self.cli), *captured["argv"]])
        self.assertEqual(log["codex_version"], "codex-cli 0.167.0-test")
        self.assertEqual(log["codex_sha256"], self.config["codex_sha256"])
        self.assertEqual((log["pid"], log["pgid"]), (pid, pid))
        self.assertNotIn("UNRELATED_SENTINEL", log["fixed_environment"])
        self.assertNotIn("synthetic prompt", json.dumps(log))

    def test_resume_preserves_original_order_and_does_not_add_unsupported_sandbox_flag(self):
        original = ["exec", "resume", "--skip-git-repo-check", "--json", "--output-schema",
                    "/tmp/schema.json", "-o", "/tmp/message.json", "test-session", "-"]
        _, code, _, _ = self.invoke(original)
        self.assertEqual(code, 0)
        captured = json.loads(self.capture.read_text())["argv"]
        count = len(captured) - len(original)
        self.assertEqual(captured[:2] + captured[2 + count:], original)
        self.assertNotIn("--sandbox", captured)
        self.assertEqual(self.config_arguments(captured)["sandbox_mode"], "workspace-write")

    def test_changed_cli_hash_blocks_before_cli_or_json_output(self):
        self.cli.write_text(FAKE_CLI + "\n# changed executable\n")
        _, code, stdout, stderr = self.invoke(["exec", "--json", "-"])
        self.assertEqual(code, 78)
        self.assertEqual(stdout, b"")
        self.assertIn(b"sha256 changed", stderr)
        self.assertFalse(self.capture.exists())
        self.assertFalse((self.root / "launcher-events.jsonl").exists())

    def test_same_launcher_and_copied_launcher_are_rejected(self):
        for copied in (False, True):
            with self.subTest(copied=copied):
                target = self.launcher
                if copied:
                    target = self.root / "other-launcher"
                    shutil.copyfile(self.launcher, target)
                    target.chmod(0o755)
                self.config.update(codex_path=str(target), codex_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
                _, code, stdout, stderr = self.invoke(["exec", "--json", "-"])
                self.assertEqual(code, 78)
                self.assertEqual(stdout, b"")
                self.assertIn(b"not the real CLI", stderr)

    def test_conflicting_runtime_options_are_rejected(self):
        variants = [
            ["--dangerously-bypass-approvals-and-sandbox"], ["--sandbox", "danger-full-access"],
            ["--model", "other-model"], ["-c", 'web_search="live"'],
            ["-c", "sandbox_workspace_write={network_access=true}"],
            ["-c", 'model_reasoning_effort="low"'],
        ]
        for options in variants:
            with self.subTest(options=options):
                _, code, stdout, _ = self.invoke(["exec", *options, "-"])
                self.assertEqual(code, 78)
                self.assertEqual(stdout, b"")
                self.assertFalse(self.capture.exists())

    def test_secret_config_is_forwarded_but_redacted_in_log(self):
        original = ["exec", "-c", 'model_providers.example.api_key="fixture-secret"',
                    '--config=model_providers.example.http_headers={Authorization="fixture-header"}', "-"]
        _, code, _, _ = self.invoke(original)
        self.assertEqual(code, 0)
        self.assertIn(original[2], json.loads(self.capture.read_text())["argv"])
        log = (self.root / "launcher-events.jsonl").read_text()
        self.assertNotIn("fixture-secret", log)
        self.assertNotIn("fixture-header", log)
        self.assertIn("<redacted>", log)

    def test_mismatched_version_and_requested_settings_are_rejected(self):
        for key, value in (("codex_version", "codex-cli changed"), ("model", "other"),
                           ("reasoning_effort", "low"), ("model_provider", "other")):
            with self.subTest(key=key):
                saved = self.config[key]
                self.config[key] = value
                _, code, stdout, _ = self.invoke(["exec", "-"])
                self.assertEqual(code, 78)
                self.assertEqual(stdout, b"")
                self.assertFalse(self.capture.exists())
                self.config[key] = saved

    def isolation_fixture(self):
        for name in ("workspace", "campaign", "codex-home", "versions/new", "versions/old", "private"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        texts = {"workspace/current.txt": "current workspace", "versions/new/current.txt": "current version",
                 "versions/old/other.txt": "other arm", "private/holdout.txt": "private holdout",
                 "private/auth-fixture.json": "disposable auth fixture"}
        for name, text in texts.items():
            (self.root / name).write_text(text)
        self.capture = self.root / "workspace/capture.json"
        self.config.update(codex_home=str(self.root / "codex-home"), isolation={
            "hidden_roots": ["/tmp", "/home/lzh/workspace"],
            "read_only": [str(self.cli), str(self.root / "versions/new"), {
                "source": str(self.root / "private/auth-fixture.json"),
                "target": str(self.root / "codex-home/auth.json")}],
            "writable": [str(self.root / name) for name in ("workspace", "campaign", "codex-home")],
        })
        return {
            "workspace": str(self.root / "workspace/current.txt"),
            "version": str(self.root / "versions/new/current.txt"),
            "other_arm": str(self.root / "versions/old/other.txt"),
            "private": str(self.root / "private/holdout.txt"),
            "auth_mapping": str(self.root / "codex-home/auth.json"),
            "host_proc_escape": f"/proc/{os.getpid()}/root" + str(self.root / "private/holdout.txt"),
        }

    @unittest.skipUnless(Path("/usr/bin/bwrap").exists(), "requires installed bubblewrap")
    def test_real_bwrap_hides_other_arm_and_private_files_preserving_streams_and_limits(self):
        probes = self.isolation_fixture()
        _, code, stdout, stderr = self.invoke(["exec", "--json", "-"], exit_code=19, payload=b"isolated input\n",
            extra_env={"FAKE_PROBES": json.dumps(probes),
                       "FAKE_READONLY": json.dumps([probes["version"], probes["auth_mapping"]])})
        self.assertEqual(code, 19, stderr.decode())
        self.assertEqual(len(stdout.splitlines()), 2)
        self.assertEqual(stderr, b"fake stderr\n")
        captured = json.loads(self.capture.read_text())
        self.assertEqual(bytes.fromhex(captured["stdin_hex"]), b"isolated input\n")
        self.assertEqual(captured["affinity"], self.config["cpu_affinity"])
        self.assertEqual(captured["environment"]["CODEX_HOME"], self.config["codex_home"])
        self.assertEqual(captured["environment"]["OMP_NUM_THREADS"], "1")
        self.assertEqual(captured["environment"]["MKL_NUM_THREADS"], "1")
        self.assertEqual(captured["environment"]["PYTHONHASHSEED"], "23")
        for name in ("workspace", "version", "auth_mapping"):
            self.assertTrue(captured["probes"][name]["readable"], name)
        for name in ("other_arm", "private", "host_proc_escape"):
            self.assertFalse(captured["probes"][name]["readable"], name)
        self.assertTrue(all(captured["readonly_write_blocked"].values()))
        event = json.loads((self.root / "launcher-events.jsonl").read_text())
        self.assertIn("--unshare-pid", event["launcher_exec_argv"])
        self.assertNotIn("--new-session", event["launcher_exec_argv"])
        self.assertNotIn("--unshare-net", event["launcher_exec_argv"])

    @unittest.skipUnless(Path("/usr/bin/bwrap").exists(), "requires installed bubblewrap")
    def test_real_bwrap_descendants_stay_in_host_group_and_killpg_stops_them(self):
        self.isolation_fixture()
        process = self.launch(["exec", "--json", "-"], extra_env={"FAKE_HOLD": "1"})
        process.stdin.close()
        process.stdin = None
        try:
            deadline = time.monotonic() + 5
            while not self.capture.exists() and time.monotonic() < deadline and process.poll() is None:
                time.sleep(0.01)
            self.assertTrue(self.capture.exists(), "isolated fake CLI did not start")
            pending, descendants = [process.pid], []
            while pending:
                parent = pending.pop()
                child_file = Path(f"/proc/{parent}/task/{parent}/children")
                children = [int(value) for value in child_file.read_text().split()]
                descendants += children
                pending += children
            self.assertTrue(descendants)
            for child in descendants:
                self.assertEqual(os.getpgid(child), process.pid)
            os.killpg(process.pid, signal.SIGTERM)
            process.communicate(timeout=5)
            self.assertNotEqual(process.returncode, 0)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
