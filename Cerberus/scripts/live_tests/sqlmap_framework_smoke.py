"""Real sqlmap integration smoke test against a disposable loopback-only lab.

Runs real sqlmap against an intentionally vulnerable SQLite query and a
parameterized control. If Nmap is installed, the three-tool scheduler exercise
also uses real Nmap. Its Metasploit endpoint is explicitly a FAKE MessagePack RPC
service; this does not test a real Metasploit msfrpcd.

The lab listens only on 127.0.0.1, uses an in-memory database for each
request, and exits without persisting its database or sqlmap output. sqlmap
must be installed separately. The --sqlmap argument can point to sqlmap.py.
"""

import argparse
import asyncio
import contextlib
import shutil
import sqlite3
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import msgpack
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
# Settings otherwise looks for .env relative to the caller's working directory.
# Preserve explicitly exported variables over the backend .env values.
load_dotenv(BACKEND_DIR / ".env", override=False)

from app.ai_engine.pentest import (  # noqa: E402
    ExecutionEngine,
    ExecutionScheduler,
    PentestContext,
    ScheduledModule,
    ScopeConfig,
)
from app.ai_engine.pentest.core import SeverityLevel  # noqa: E402
from app.core.config import settings  # noqa: E402


class LabHandler(BaseHTTPRequestHandler):
    """A small lab with vulnerable and parameterized SQLite queries."""

    destination = ""
    redirect_requests = 0
    refresh_requests = 0
    alias_observations = []
    alias_lock = threading.Lock()

    def handle(self):
        # Nmap opens and closes a TCP connection without an HTTP request.
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            super().handle()

    def do_GET(self):  # noqa: N802
        self._respond("GET")

    def do_POST(self):  # noqa: N802
        self._respond("POST")

    def _respond(self, method: str) -> None:
        parts = urlsplit(self.path)
        if parts.path == "/redirect":
            type(self).redirect_requests += 1
            self.send_response(302)
            self.send_header("Location", type(self).destination)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if parts.path == "/refresh":
            type(self).refresh_requests += 1
            content = (
                '<html><head><meta http-equiv="refresh" content="0;url='
                + type(self).destination
                + '"></head><body>refresh</body></html>'
            ).encode("ascii")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if method == "POST":
            length = int(self.headers.get("Content-Length", "0"))
            source = self.rfile.read(length).decode("ascii", errors="replace")
        else:
            source = parts.query
        parameters = parse_qs(source, keep_blank_values=True)
        parameter_name = "id"
        if parts.path == "/alias":
            parameter_name = "cookie" if method == "GET" else "useragent"
            # Test-only values: capture every request to verify that sqlmap
            # changes only the selected request parameter, not auth headers.
            with type(self).alias_lock:
                type(self).alias_observations.append(
                    {
                        "method": method,
                        "parameters": parameters,
                        "cookie": self.headers.get("Cookie", ""),
                        "agent": self.headers.get("User-Agent", ""),
                    }
                )
        parameter = parameters.get(parameter_name, ["1"])[0]
        database = sqlite3.connect(":memory:")
        try:
            database.executescript(
                "CREATE TABLE users(id INTEGER, name TEXT);"
                "INSERT INTO users VALUES (1,'alpha'),(2,'bravo'),(3,'charlie');"
            )
            if parts.path == "/safe":
                rows = database.execute(
                    "SELECT name FROM users WHERE id = ?", (parameter,)
                ).fetchall()
            else:
                # Deliberately vulnerable, isolated demonstration code only.
                rows = database.execute(f"SELECT name FROM users WHERE id = {parameter}").fetchall()
            body = (
                "<html><body>"
                + (
                    "Results: " + ",".join(row[0] for row in rows)
                    if rows
                    else "No matching records"
                )
                + "</body></html>"
            )
            status = 200
        except sqlite3.Error as exc:
            body = f"sqlite3.OperationalError: {exc}"
            status = 500
        finally:
            database.close()
        content = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *args):
        pass


class RedirectSink(BaseHTTPRequestHandler):
    """A different local port, deliberately outside the lab scope."""

    hits = 0

    def do_GET(self):  # noqa: N802
        type(self).hits += 1
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


class _FakeRpcHandler(BaseHTTPRequestHandler):
    """MessagePack HTTP transport only: this service is not Metasploit."""

    def do_POST(self):  # noqa: N802
        try:
            assert self.path == "/api/"
            assert self.headers.get("Content-Type") == "binary/message-pack"
            length = int(self.headers["Content-Length"])
            request = msgpack.unpackb(self.rfile.read(length), raw=False)
            response = self.server.service.dispatch(*request)
            encoded = msgpack.packb(response, use_bin_type=True)
            self.send_response(200)
            self.send_header("Content-Type", "binary/message-pack")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except Exception:
            self.send_error(500)

    def log_message(self, *args):
        pass


class FakeMetasploitRpc:
    """Clearly simulated msfrpcd; no actual Metasploit scanning is performed."""

    def __init__(self, scanned_port: int):
        self.scanned_port = scanned_port
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeRpcHandler)
        self.server.service = self
        self.port = self.server.server_address[1]
        self.pending = ""
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def dispatch(self, method: str, *args):
        if method == "auth.login":
            username, password = args
            if username != "msf" or password != "test-only-password":
                return {"result": "failed"}
            return {"result": "success", "token": "fake-token"}
        token, *rest = args
        if token != "fake-token":
            raise ValueError("invalid test token")
        if method == "auth.logout":
            assert rest == [token]
            return {"result": "success"}
        if method == "core.version":
            return {"version": "FAKE-TEST-SERVICE"}
        if method == "console.create":
            return {"id": "1", "busy": False}
        if method == "console.write":
            _, data = rest
            marker = next(
                line[4:] for line in data.splitlines() if line.startswith("get CERBERUS_SYNC_")
            )
            self.pending = (
                f"[*] 127.0.0.1:{self.scanned_port} - TCP OPEN\n"
                "[*] Auxiliary module execution completed\n" + marker + " => \n"
            )
            return {"wrote": len(data.encode("utf-8"))}
        if method == "console.read":
            output, self.pending = self.pending, ""
            return {"data": output, "busy": False}
        if method == "console.destroy":
            return {"result": "success"}
        raise ValueError(f"unexpected fake RPC method: {method}")

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _context(port: int, path: str, **config) -> PentestContext:
    return PentestContext(
        target=f"http://127.0.0.1:{port}/{path}",
        scope=ScopeConfig(
            allowed_targets=["127.0.0.1"],
            allowed_ports=[port],
            max_impact="limited",
            request_delay=0.0,
        ),
        config={
            "sqlmap_timeout": 60,
            "nmap_ports": [port],
            "nmap_service_version": False,
            "msf_options": {"PORTS": str(port)},
            **config,
        },
    )


def _assert_no_errors(findings) -> None:
    failures = [finding.title for finding in findings if finding.severity == SeverityLevel.ERROR]
    if failures:
        raise RuntimeError("Unexpected error findings: " + ", ".join(failures))


async def exercise(sqlmap_path: str | None) -> None:
    if sqlmap_path:
        settings.SQLMAP_PATH = sqlmap_path
    settings.SQLMAP_ENABLED = True
    # This is a local toy target; no production settings are changed.
    settings.PENTEST_REQUEST_DELAY = 0.0
    settings.PENTEST_MODULE_TIMEOUT = 90

    sink = ThreadingHTTPServer(("127.0.0.1", 0), RedirectSink)
    sink_thread = threading.Thread(target=sink.serve_forever, daemon=True)
    sink_thread.start()
    LabHandler.destination = f"http://127.0.0.1:{sink.server_address[1]}/outside"
    LabHandler.redirect_requests = 0
    LabHandler.refresh_requests = 0
    LabHandler.alias_observations = []
    RedirectSink.hits = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), LabHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    port = server.server_address[1]
    fake_rpc = FakeMetasploitRpc(port)
    fake_rpc.start()
    try:
        settings.MSF_ENABLED = True
        settings.MSF_RPC_HOST = "127.0.0.1"
        settings.MSF_RPC_PORT = fake_rpc.port
        settings.MSF_RPC_PASSWORD = "test-only-password"
        settings.MSF_RPC_SSL = False
        settings.NMAP_ENABLED = bool(shutil.which(settings.NMAP_PATH))

        engine = ExecutionEngine()
        scheduler = ExecutionScheduler(engine)
        vulnerable = _context(port, "vulnerable?id=1")
        names = ["sqlmap_scanner", "metasploit_scanner"]
        if settings.NMAP_ENABLED:
            names.insert(0, "nmap_scanner")
        else:
            print("SKIP: real Nmap is not installed; sqlmap and fake Metasploit will still run.")
        report = await scheduler.run(
            [ScheduledModule(module_name=name) for name in names], vulnerable
        )
        _assert_no_errors(report.findings)
        if not any(
            item.module_name == "sqlmap_scanner" and item.severity == SeverityLevel.HIGH
            for item in report.findings
        ):
            raise RuntimeError("Real sqlmap did not identify the vulnerable local GET parameter.")
        if settings.NMAP_ENABLED:
            nmap = next(item for item in report.findings if item.module_name == "nmap_scanner")
            if port not in nmap.metadata.get("open_ports", []):
                raise RuntimeError("Real Nmap did not identify the lab's open port.")
        msf = next(item for item in report.findings if item.module_name == "metasploit_scanner")
        if port not in msf.metadata.get("open_ports", []):
            raise RuntimeError("The simulated Metasploit output was not parsed.")
        print(f"PASS: scheduled {', '.join(names)}; real sqlmap detected GET SQLi")
        print("NOTE: Nmap is real when present; the Metasploit RPC service is a test double.")

        safe = await engine.execute("sqlmap_scanner", _context(port, "safe?id=1"))
        _assert_no_errors(safe)
        if any(item.is_actionable() for item in safe):
            raise RuntimeError("The parameterized control unexpectedly produced a vulnerability.")
        if not any("No SQL injection identified" in item.title for item in safe):
            raise RuntimeError("The parameterized control did not complete a recognizable scan.")
        print("PASS: parameterized GET control produced no actionable finding")

        post_context = _context(port, "vulnerable", sqlmap_method="POST", sqlmap_data="id=1")
        post = await engine.execute("sqlmap_scanner", post_context)
        _assert_no_errors(post)
        if not any(
            item.severity == SeverityLevel.HIGH and item.metadata.get("method") == "POST"
            for item in post
        ):
            raise RuntimeError("Real sqlmap did not identify the vulnerable local POST parameter.")
        print("PASS: real sqlmap detected SQLi in an authorized form POST")

        # SQLmap treats names such as cookie and useragent as header aliases
        # when passed through -p. Exercise the safe selection fallback with a
        # real binary, both request methods, case-sensitive unselected fields,
        # and asterisk-containing test credentials.
        alias_get = _context(
            port,
            "alias?cookie=1&COOKIE=case_value&GET=method_value&other=untouched",
            sqlmap_parameters=["cookie"],
        )
        alias_get.auth_cookies = {"session": "trust*ed"}
        alias_post = _context(
            port,
            "alias",
            sqlmap_method="POST",
            sqlmap_data="useragent=1&USERAGENT=case_value&POST=method_value&other=untouched",
            sqlmap_parameters=["useragent"],
        )
        alias_post.auth_headers = {"User-Agent": "trust*ed-agent"}
        for method, name, ctx in (("GET", "cookie", alias_get), ("POST", "useragent", alias_post)):
            findings = await engine.execute("sqlmap_scanner", ctx)
            _assert_no_errors(findings)
            if not any(
                item.is_actionable() and item.metadata.get("parameter") == name for item in findings
            ):
                raise RuntimeError(
                    f"Real sqlmap did not scan the selected {method} alias parameter."
                )
            records = [item for item in LabHandler.alias_observations if item["method"] == method]
            if not records or not any(
                record["parameters"].get(name, [""])[0] != "1" for record in records
            ):
                raise RuntimeError(f"The selected {method} parameter was not actually tested.")
            case_name = "COOKIE" if method == "GET" else "USERAGENT"
            if any(
                record["parameters"].get(case_name) != ["case_value"]
                or record["parameters"].get(method) != ["method_value"]
                or record["parameters"].get("other") != ["untouched"]
                for record in records
            ):
                raise RuntimeError(f"An unselected {method} parameter was modified.")
            if method == "GET" and any(
                record["cookie"] != "session=trust*ed" for record in records
            ):
                raise RuntimeError("The GET scan modified the test authentication cookie.")
            if method == "POST" and any(record["agent"] != "trust*ed-agent" for record in records):
                raise RuntimeError("The POST scan modified the test User-Agent header.")
        print("PASS: selected GET/POST alias parameters left auth and unselected fields unchanged")

        for path in ("redirect?id=1", "refresh?id=1"):
            await engine.execute("sqlmap_scanner", _context(port, path))
        if not LabHandler.redirect_requests or not LabHandler.refresh_requests or RedirectSink.hits:
            raise RuntimeError("A redirect/refresh escaped the approved lab scope.")
        print("PASS: out-of-scope HTTP redirects and HTML refreshes were not followed")

        first = _context(port, "vulnerable?id=1")
        second = _context(port, "vulnerable?id=2")
        parallel = await asyncio.gather(
            engine.execute("sqlmap_scanner", first),
            engine.execute("sqlmap_scanner", second),
        )
        if any(not any(item.is_actionable() for item in findings) for findings in parallel):
            raise RuntimeError("One of two independent concurrent sqlmap runs failed.")
        if first.shared_state is second.shared_state:
            raise RuntimeError("Independent engagements shared state unexpectedly.")
        print("PASS: two real sqlmap scans ran concurrently in isolated engagements")
        if settings.NMAP_ENABLED:
            concurrent_contexts = [_context(port, "vulnerable?id=1") for _ in range(3)]
            concurrent = await asyncio.gather(
                engine.execute("nmap_scanner", concurrent_contexts[0]),
                engine.execute("sqlmap_scanner", concurrent_contexts[1]),
                engine.execute("metasploit_scanner", concurrent_contexts[2]),
            )
            for findings in concurrent:
                _assert_no_errors(findings)
            if port not in concurrent[0][0].metadata.get("open_ports", []):
                raise RuntimeError("Concurrent real Nmap scan did not report the lab port.")
            if not any(item.is_actionable() for item in concurrent[1]):
                raise RuntimeError("Concurrent real sqlmap scan did not identify the SQLi.")
            if port not in concurrent[2][0].metadata.get("open_ports", []):
                raise RuntimeError("Concurrent fake Metasploit scan did not produce its result.")
            print(
                "PASS: real Nmap + real sqlmap + fake Metasploit ran "
                "in separate concurrent engagements"
            )
        print("PASS: the local lab and temporary sqlmap scan files were cleaned up")
    finally:
        fake_rpc.stop()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
        sink.shutdown()
        sink.server_close()
        sink_thread.join(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlmap", help="sqlmap executable or path to the official sqlmap.py")
    args = parser.parse_args()
    asyncio.run(exercise(args.sqlmap))


if __name__ == "__main__":
    main()
