from __future__ import annotations

import contextlib
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.error
import urllib.parse
import ssl


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "kaggle_sources.py"
SPEC = importlib.util.spec_from_file_location("kaggle_sources_under_test", SCRIPT)
kaggle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kaggle)

TOPIC_URL = "https://www.kaggle.com/competitions/wheat/discussion/77"
NOTEBOOK_URL = "https://www.kaggle.com/code/alice/wheat-model"
TOPIC_REQUEST = {"forumTopicId": 77, "includeComments": True, "initialPageSize": 200}
TOPIC = {
    "forum_topic": {
        "id": 77,
        "url": "/competitions/wheat/discussion/77",
        "name": "A measured method",
        "total_messages": 90,
        "first_message": {"raw_markdown": "Method: café; a server error is discussed as evidence."},
        "comments": [
            {"id": 101, "raw_markdown": "First comment with details", "author": {"display_name": "Ann"},
             "replies": [
                 {"id": 111, "raw_markdown": "Reply one", "replies": [
                     {"id": 112, "raw_markdown": "Nested reply"}]},
                 {"id": 113, "raw_markdown": "Reply two"},
             ]},
            {"id": 102, "content": "<p>Second <b>comment</b></p><script>not prose</script>"},
        ],
    }
}


def wire(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def rpc(value):
    return {"jsonrpc": "2.0", "id": 1,
            "result": {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}}


def mcp_step(tool, request, value, *, raw=None, status=200):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": tool, "arguments": {"request": request}}}
    return ("/mcp", payload, wire(rpc(value)) if raw is None else raw, status)


def web_step(endpoint, request, value):
    return ("/api/i/" + endpoint, request, value if isinstance(value, bytes) else wire(value), 200)


class FixedResponse:
    def __init__(self, raw, status):
        self.raw, self.status = raw, status
        self.stream = io.BytesIO(raw)
        self.headers = {"Content-Type": "application/json; charset=utf-8"}

    def read(self):
        return self.raw

    def read1(self, size):
        return self.stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FixedOpener:
    """Consume only explicit request/response pairs; any unexpected request fails."""

    def __init__(self, case, steps):
        self.case, self.steps, self.calls = case, list(steps), []

    def open(self, request, timeout):
        self.case.assertTrue(self.steps, "Unexpected request: " + request.full_url)
        path, payload, raw, status = self.steps.pop(0)
        actual_payload = json.loads(request.data) if request.data is not None else None
        self.case.assertEqual(urllib.parse.urlsplit(request.full_url).hostname, "www.kaggle.com")
        self.case.assertEqual(urllib.parse.urlsplit(request.full_url).path, path)
        self.case.assertEqual(actual_payload, payload)
        self.calls.append((path, actual_payload))
        if status != 200:
            raise urllib.error.HTTPError(request.full_url, status, "fixture failure", {}, io.BytesIO(raw))
        return FixedResponse(raw, status)


class KaggleSourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="kaggle-source-tests-", dir=os.environ.get("TMPDIR") or None)
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "sources"
        self.addCleanup(mock.patch.stopall)
        mock.patch.dict(os.environ, {"KAGGLE_API_TOKEN": "", "KAGGLE_CONFIG_DIR": str(Path(self.temporary.name) / ".kaggle")}).start()
        mock.patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("Network forbidden in tests")).start()

    def args(self, *extra, command="read"):
        argv = [command, "--output-dir", str(self.output)]
        if command == "read":
            argv += ["--url", TOPIC_URL]
        else:
            argv += ["--competition", "wheat", "--question", "representation"]
        return kaggle.parse_args(argv + list(extra))

    def client(self, *steps):
        client = kaggle.Client()
        client.opener = FixedOpener(self, steps)
        self.addCleanup(lambda: self.assertEqual(client.opener.steps, [], "Expected requests not made"))
        return client

    def topic_client(self, value=None, request=None, **kwargs):
        return self.client(mcp_step("get_forum_topic", request or TOPIC_REQUEST,
                                    TOPIC if value is None else value, **kwargs))

    def test_standard_token_file_authenticates_without_entering_snapshots_and_env_takes_precedence(self):
        token_file = Path(os.environ["KAGGLE_CONFIG_DIR"]) / "access_token"
        token_file.parent.mkdir()
        token_file.write_text("fixture-file-token\n")
        client = self.topic_client()
        with mock.patch.object(client.opener, "open", wraps=client.opener.open) as opened:
            result = kaggle.run(self.args(), client)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(opened.call_args.args[0].get_header("Authorization"), "Bearer fixture-file-token")
        for path in Path(result["snapshot"]).iterdir():
            self.assertNotIn(b"fixture-file-token", path.read_bytes())
        with mock.patch.dict(os.environ, {"KAGGLE_API_TOKEN": "fixture-environment-token"}):
            self.assertEqual(kaggle.Client().token, "fixture-environment-token")

    def test_transport_retry_recovers_and_archives_each_attempt(self):
        client = kaggle.Client(retries=2)
        partial = b"data: incomplete response"
        interrupted = FixedResponse(b"", 200)
        interrupted.read1 = mock.Mock(side_effect=[partial, TimeoutError("read timed out")])
        complete = wire(rpc(TOPIC))
        with mock.patch.object(client.opener, "open", side_effect=[
                urllib.error.URLError(TimeoutError("handshake timed out")), interrupted,
                FixedResponse(complete, 200)]) as opened, mock.patch.object(kaggle.time, "sleep") as slept:
            result = kaggle.run(self.args(), client)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(opened.call_count, 3)
        self.assertEqual([call.args[0].data for call in opened.call_args_list], [opened.call_args.args[0].data] * 3)
        self.assertEqual(slept.call_args_list, [mock.call(1), mock.call(2)])
        snapshot = Path(result["snapshot"])
        self.assertEqual([(snapshot / f"response-{i:03d}.bin").read_bytes() for i in range(3)],
                         [b"", partial, complete])
        requests = json.loads((snapshot / "requests.json").read_bytes())
        self.assertEqual([row["attempt"] for row in requests], [1, 2, 3])
        self.assertEqual([row["status"] for row in requests], [None, 200, 200])
        self.assertEqual([row["response_complete"] for row in requests], [False, False, True])
        self.assertEqual(requests[1]["response_sha256"], hashlib.sha256(partial).hexdigest())
        self.assertEqual(result["request_count"], 3)

    def test_exhausted_or_disabled_transport_retries_remain_failures_without_a_cache(self):
        for retries in (0, 2):
            with self.subTest(retries=retries):
                args = self.args("--retries", str(retries))
                args.output_dir = self.output / str(retries)
                with mock.patch("urllib.request.OpenerDirector.open", side_effect=TimeoutError("timed out")) as opened, \
                        mock.patch.object(kaggle.time, "sleep"):
                    result = kaggle.run(args)
                self.assertEqual(result["status"], "error")
                self.assertEqual(opened.call_count, retries + 1)
                self.assertEqual(result["request_count"], retries + 1)
                self.assertEqual(list(args.output_dir.glob("cache-*.json")), [])

    def test_premature_eof_does_not_accept_a_truncated_http_body(self):
        client = kaggle.Client(retries=1)
        partial = FixedResponse(b"truncated", 200)
        partial.length = 15
        with mock.patch.object(client.opener, "open", side_effect=[partial, FixedResponse(wire(rpc(TOPIC)), 200)]), \
                mock.patch.object(kaggle.time, "sleep"):
            result = kaggle.run(self.args(), client)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["request_count"], 2)
        self.assertFalse(client.requests[0]["response_complete"])
        self.assertEqual(client.responses[0], b"truncated")
        self.assertIn("IncompleteRead", client.requests[0]["error"])

    def test_gzip_reduces_transfer_without_changing_body_or_original_response_bytes(self):
        client = kaggle.Client()
        original = wire(rpc(TOPIC))
        compressed = gzip.compress(original)
        response = FixedResponse(compressed, 200)
        response.headers["Content-Encoding"] = "gzip"
        with mock.patch.object(client.opener, "open", return_value=response) as opened:
            result = kaggle.run(self.args(), client)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["view"]["body"], TOPIC["forum_topic"]["first_message"]["raw_markdown"])
        self.assertEqual(opened.call_args.args[0].get_header("Accept-encoding"), "gzip")
        self.assertEqual((Path(result["snapshot"]) / "response-000.bin").read_bytes(), compressed)
        self.assertEqual(client.requests[0]["content_encoding"], "gzip")
        self.assertEqual(client.requests[0]["response_bytes"], len(compressed))
        self.assertEqual(client.requests[0]["decoded_bytes"], len(original))
        self.assertEqual(client.requests[0]["response_sha256"], hashlib.sha256(compressed).hexdigest())

    def test_invalid_compression_is_archived_as_failure_without_retry(self):
        for index, (encoding, body) in enumerate((("gzip", b"not-gzip"), ("gzip", gzip.compress(wire(rpc(TOPIC)))[:-4]),
                                                 ("br", b"unsupported"))):
            with self.subTest(encoding=encoding, index=index):
                response = FixedResponse(body, 200)
                response.headers["Content-Encoding"] = encoding
                args = self.args()
                args.output_dir = self.output / str(index)
                with mock.patch("urllib.request.OpenerDirector.open", return_value=response) as opened:
                    result = kaggle.run(args)
                self.assertEqual(result["status"], "error")
                self.assertEqual(opened.call_count, 1)
                self.assertEqual((Path(result["snapshot"]) / "response-000.bin").read_bytes(), body)
                self.assertEqual(list(args.output_dir.glob("cache-*.json")), [])

    def test_certificate_failures_and_http_errors_are_not_retried(self):
        cases = [urllib.error.URLError(ssl.SSLCertVerificationError("certificate mismatch"))]
        cases.extend(urllib.error.HTTPError(kaggle.BASE + "/mcp", status, "rejected", {}, io.BytesIO(b"failure"))
                     for status in (401, 403, 404, 503))
        for index, error in enumerate(cases):
            with self.subTest(error=type(error).__name__, index=index):
                args = self.args()
                args.output_dir = self.output / str(index)
                with mock.patch("urllib.request.OpenerDirector.open", side_effect=error) as opened, \
                        mock.patch.object(kaggle.time, "sleep") as slept:
                    result = kaggle.run(args)
                self.assertEqual(result["status"], "error")
                self.assertEqual(opened.call_count, 1)
                slept.assert_not_called()

    def test_tcp_mss_is_set_before_connect_and_failed_address_socket_is_closed(self):
        first, second = mock.Mock(), mock.Mock()
        first.connect.side_effect = TimeoutError("first address unavailable")
        addresses = [(kaggle.socket.AF_INET, kaggle.socket.SOCK_STREAM, 6, "", ("192.0.2.1", 443)),
                     (kaggle.socket.AF_INET, kaggle.socket.SOCK_STREAM, 6, "", ("192.0.2.2", 443))]
        events = mock.Mock()
        events.attach_mock(second.setsockopt, "setsockopt")
        events.attach_mock(second.settimeout, "settimeout")
        events.attach_mock(second.connect, "connect")
        with mock.patch.object(kaggle.socket, "getaddrinfo", return_value=addresses), \
                mock.patch.object(kaggle.socket, "socket", side_effect=[first, second]):
            result = kaggle._connect_with_mss(("www.kaggle.com", 443), 15, tcp_mss=1200)
        self.assertIs(result, second)
        first.close.assert_called_once()
        second.close.assert_not_called()
        self.assertEqual(events.mock_calls, [mock.call.setsockopt(kaggle.socket.IPPROTO_TCP, kaggle.socket.TCP_MAXSEG, 1200),
                                            mock.call.settimeout(15), mock.call.connect(("192.0.2.2", 443))])

    def test_tcp_mss_handler_preserves_tls_verification_and_records_requested_setting(self):
        client = kaggle.Client(direct=True, tcp_mss=1200)
        handler = next(handler for handler in client.opener.handlers if isinstance(handler, kaggle._MSSHTTPSHandler))
        context = handler._context
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        request = urllib.request.Request(kaggle.BASE)
        with mock.patch.object(handler, "do_open") as opened:
            handler.https_open(request)
        factory = opened.call_args.args[0]
        with mock.patch.object(kaggle.http.client, "HTTPSConnection") as connection, \
                mock.patch.object(kaggle, "_connect_with_mss") as connect:
            factory("www.kaggle.com", timeout=15, context=context)
            connection.return_value._create_connection(("www.kaggle.com", 443), 15)
        connect.assert_called_once_with(("www.kaggle.com", 443), 15, None, tcp_mss=1200)
        client.opener = FixedOpener(self, [mcp_step("get_forum_topic", TOPIC_REQUEST, TOPIC)])
        result = kaggle.run(self.args("--direct", "--tcp-mss", "1200"), client)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(client.requests[0]["tcp_mss"], 1200)
        self.assertEqual(client.requests[0]["network_mode"], "direct")

    def notebook_steps(self, *, rows=None, source=b"print('historical')\r\n", page_token=None):
        if rows is None:
            rows = [
                {"version": {"versionNumber": 2, "id": 9002}, "run": {"id": 202, "title": "Historical"}},
                {"version": {"versionNumber": 3, "id": 9003}, "run": {"id": 303, "title": "Latest"}},
            ]
        request = {"kernelId": 501, "sortOption": "VERSION_ID", "pageSize": 200}
        if page_token:
            request["pageToken"] = page_token
        steps = [
            ("/", None, b"<html>public session</html>", 200),
            web_step(kaggle.VIEW, {"authorUserName": "alice", "kernelSlug": "wheat-model", "tab": "output"},
                     {"kernel": {"id": 501}, "kernelRun": {"id": 303}, "totalVersionCount": 70}),
            web_step(kaggle.VERSIONS, request, {"items": rows, "nextPageToken": "older-versions"}),
        ]
        if source is not None:
            steps.append(web_step(kaggle.SOURCE, {"kernelSessionId": 202, "includeOutputIfAvailable": False}, source))
        return steps

    def test_discovery_joins_same_board_teams_and_keeps_score_zero_without_borrowing_public_rank(self):
        board = {
            "privateLeaderboard": [
                {"teamId": 10, "rank": 1, "displayScore": "0.62"},
                {"teamId": 20, "rank": 2, "score": 0},
            ],
            "publicLeaderboard": [{"teamId": 20, "rank": 1, "score": "0.99"}],
            "teams": [
                {"teamId": 20, "teamName": "Second", "solutionWriteUpUrl": "/competitions/wheat/writeups/second"},
                {"teamId": 10, "teamName": "First", "solutionWriteUpUrl": "/competitions/wheat/writeups/first"},
                {"teamId": 30, "teamName": "Unranked", "solutionWriteUpUrl": "/competitions/wheat/writeups/no-match"},
            ],
        }
        client = self.discovery_client(board, {"topics": []})
        result = kaggle.run(self.args(command="discover"), client)
        self.assertEqual(result["status"], "ok")
        sources = result["source"]["sources"]
        self.assertEqual([(row["team_id"], row["rank"], row["score"], row["board"]) for row in sources],
                         [(10, 1, "0.62", "private"), (20, 2, 0, "private")])
        self.assertTrue(all(row["competition"] == "wheat" for row in sources))

    def test_discovery_counts_retain_entity_population_and_raw_response_identity_across_cache(self):
        board = {"publicLeaderboard": [{"teamId": i} for i in range(3)], "teams": []}
        topics = [{"id": i, "topic_url": f"/competitions/wheat/discussion/{i}"} for i in (11, 12)]
        result = kaggle.run(self.args("--page-size", "1", command="discover"),
                            self.discovery_client(board, {"count": 19, "topics": topics}))
        quantities = {row["name"]: row for row in result["source"]["quantities"]}
        entries = quantities["returned_leaderboard_entries"]
        self.assertEqual((entries["value"], entries["entity"], entries["unit"]), (3, "leaderboard_entry", "entries"))
        self.assertEqual(entries["scope"], {"competition": "wheat", "board": "public", "population": "returned_response"})
        snapshot = Path(result["snapshot"])
        for row in quantities.values():
            raw = (snapshot / row["basis"]["response_file"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row["basis"]["response_sha256"])
        board_raw = json.loads((snapshot / entries["basis"]["response_file"]).read_bytes())
        self.assertEqual(entries["value"], len(board_raw["publicLeaderboard"]))
        returned, matches = quantities["returned_search_topics"], quantities["server_search_matches"]
        self.assertEqual((returned["value"], matches["value"]), (2, 19))
        self.assertNotEqual(returned["scope"]["population"], matches["scope"]["population"])
        self.assertEqual(returned["scope"]["query"], "representation")
        self.assertEqual(returned["scope"]["page"], 1)
        cached = kaggle.run(self.args(command="discover"), self.client())
        self.assertTrue(cached["cache_hit"])
        self.assertEqual(cached["source"]["quantities"], result["source"]["quantities"])

    def test_failed_or_absent_source_counts_are_not_fabricated_as_zero_quantities(self):
        result = kaggle.run(self.args(command="discover"), self.discovery_client({}, {}, board_status=503))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["source"]["quantities"], [])
        self.assertEqual(result["source"]["errors"][0]["operation"], "leaderboard")

    def discovery_client(self, board, search, *, facts=None, board_status=200, search_raw=None, search_page=1):
        facts = facts or {"id": 8, "competitionName": "wheat", "url": "/competitions/wheat", "forumId": 167}
        search_request = {"forumId": 167, "hasForumId": True, "searchQuery": "representation", "hasSearchQuery": True,
                          "sortBy": "Relevance", "page": search_page, "category": "Competitions", "group": "All"}
        steps = [
            ("/", None, b"<html></html>", 200),
            web_step("competitions.CompetitionService/GetCompetition", {"competitionName": "wheat"},
                     facts),
            ("/api/i/competitions.LeaderboardService/GetLeaderboard", {"competitionId": 8}, wire(board), board_status),
        ]
        if facts.get("forumId"):
            steps.append(mcp_step("list_forum_topics", search_request, search, raw=search_raw))
        return self.client(*steps)

    def test_discovery_excludes_other_competition_and_keeps_unknown_scope_and_search_rank_unknown(self):
        client = self.discovery_client({"privateLeaderboard": [], "publicLeaderboard": [], "teams": []}, {
            "topics": [
                {"title": "1st place claim", "topic_url": "/discussions/general/88"},
                {"title": "In scope", "topic_url": "/competitions/wheat/discussion/89"},
                {"title": "Foreign", "topic_url": "/competitions/other/discussion/90"},
            ]})
        result = kaggle.run(self.args(command="discover"), client)
        self.assertEqual(result["status"], "partial")
        unknown, scoped = result["source"]["sources"]
        self.assertIsNone(unknown["competition"])
        self.assertEqual(unknown["competition_verification"], "request_filter_only")
        self.assertIsNone(unknown["rank"])
        self.assertIsNone(unknown["board"])
        self.assertEqual(scoped["competition"], "wheat")
        self.assertEqual(result["source"]["errors"][0]["operation"], "search_identity")

    def test_wrong_competition_identity_stops_before_leaderboard_or_search(self):
        client = self.client(
            ("/", None, b"<html></html>", 200),
            web_step("competitions.CompetitionService/GetCompetition", {"competitionName": "wheat"},
                     {"id": 9, "competitionName": "other", "url": "/competitions/other"}))
        result = kaggle.run(self.args(command="discover"), client)
        self.assertEqual(result["status"], "error")
        self.assertEqual(len(client.requests), 2)

    def test_discovery_transport_and_rpc_failures_do_not_become_successful_empty_results(self):
        failure = wire({"jsonrpc": "2.0", "id": 1, "result": {"isError": True, "content": []}})
        client = self.discovery_client({}, {}, board_status=503, search_raw=failure)
        result = kaggle.run(self.args(command="discover"), client)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["source"]["sources"], [])
        self.assertEqual({row["operation"] for row in result["source"]["errors"]}, {"leaderboard", "forum_search"})
        self.assertEqual(list(self.output.glob("cache-*.json")), [])

    def test_scoped_forum_search_uses_returned_parent_and_does_not_assign_a_writeup_rank(self):
        result = kaggle.run(self.args(command="discover"), self.discovery_client(
            {"privateLeaderboard": [], "publicLeaderboard": [], "teams": []}, {"count": "2", "topics": [
                {"id": 88, "title": "Method", "topic_url": "/discussions/general/88",
                 "parent_url": "/competitions/wheat/discussion"},
                {"id": 89, "title": "A winner claim", "topic_url": "/competitions/wheat/writeups/method",
                 "parent_url": "/competitions/wheat/discussion"}]}))
        self.assertEqual(result["status"], "ok")
        general, writeup = result["source"]["sources"]
        self.assertEqual(general["competition_verification"], "returned_parent_url")
        self.assertEqual(general["competition"], "wheat")
        self.assertEqual(writeup["topic_id"], 89)
        self.assertIsNone(writeup["rank"])
        self.assertEqual(result["source"]["coverage"]["server_search_count"], 2)

    def test_empty_forum_search_is_valid_but_missing_topic_shape_is_reported(self):
        board = {"privateLeaderboard": [], "publicLeaderboard": [], "teams": []}
        for index, value in enumerate(({}, {"count": "0"}, {"topics": []}, {"documents": []}, {"count": "8"})):
            with self.subTest(value=value):
                args = self.args(command="discover")
                args.output_dir = self.output / str(index)
                result = kaggle.run(args, self.discovery_client(board, value))
                self.assertEqual(result["status"], "ok" if index < 3 else "partial")
                self.assertEqual(result["source"]["sources"], [])
                if index >= 3:
                    self.assertEqual(result["source"]["errors"][0]["operation"], "forum_search")

    def test_missing_forum_identity_keeps_board_and_does_not_query_global_search(self):
        client = self.discovery_client({"privateLeaderboard": [], "publicLeaderboard": [], "teams": []}, {},
                                       facts={"id": 8, "competitionName": "wheat", "url": "/competitions/wheat"})
        result = kaggle.run(self.args(command="discover"), client)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["source"]["errors"][0]["operation"], "forum_search")
        self.assertEqual(len(client.requests), 3)

    def test_search_display_expansion_reuses_cache_but_another_server_page_is_separate(self):
        board = {"privateLeaderboard": [], "publicLeaderboard": [], "teams": []}
        search = {"count": "3", "topics": [
            {"id": 88, "title": "One", "topic_url": "/competitions/wheat/discussion/88"},
            {"id": 89, "title": "Two", "topic_url": "/competitions/wheat/discussion/89"}]}
        first = kaggle.run(self.args("--page-size", "1", command="discover"), self.discovery_client(board, search))
        self.assertEqual(len(first["source"]["sources"]), 1)
        self.assertEqual(first["source"]["coverage"]["omitted_search_topics"], 1)
        self.assertEqual(len(json.loads(Path(first["source_path"]).read_bytes())["sources"]), 2)
        expanded = kaggle.run(self.args(command="discover"), self.client())
        self.assertTrue(expanded["cache_hit"])
        self.assertEqual(expanded["snapshot"], first["snapshot"])
        self.assertEqual(len(expanded["source"]["sources"]), 2)
        second = kaggle.run(self.args("--search-page", "2", command="discover"),
                           self.discovery_client(board, {"count": "3", "topics": [
                               {"id": 90, "topic_url": "/competitions/wheat/discussion/90"}]}, search_page=2))
        self.assertFalse(second["cache_hit"])
        self.assertNotEqual(second["snapshot"], first["snapshot"])
        self.assertEqual(second["source"]["coverage"]["search_page"], 2)

    def test_source_format_exposes_all_leads_without_an_envelope_parser_or_new_requests(self):
        search = {"count": "20", "topics": [
            {"id": i, "title": f"Mechanism {i}", "topic_url": f"/competitions/wheat/discussion/{i}"}
            for i in range(20)]}
        result = kaggle.run(self.args("--page-size", "1", command="discover"),
                            self.discovery_client({"privateLeaderboard": [], "publicLeaderboard": [], "teams": []}, search))
        original = Path(result["source_path"]).read_bytes()
        for output_format in ("json", "source"):
            with self.subTest(output_format=output_format):
                output = io.StringIO()
                with mock.patch.object(kaggle, "Client", return_value=self.client()), contextlib.redirect_stdout(output):
                    code = kaggle.main(["discover", "--competition", "wheat", "--question", "representation",
                                        "--page-size", "1", "--output-dir", str(self.output),
                                        "--format", output_format])
                self.assertEqual(code, 0)
                document = json.loads(output.getvalue())
                source = document["source"] if output_format == "json" else document
                self.assertEqual(len(source["sources"]), 1 if output_format == "json" else 20)
                self.assertEqual(source["coverage"]["returned_search_topics"], 20)
                self.assertEqual(source["errors"], [])
                if output_format == "json":
                    self.assertTrue(document["cache_hit"])
                else:
                    self.assertEqual(document, json.loads(original))
        self.assertEqual(Path(result["source_path"]).read_bytes(), original)

    def test_source_format_retains_partial_errors_and_nonzero_failure_exit(self):
        for index, (board_status, expected_exit) in enumerate(((200, 0), (503, 1))):
            with self.subTest(board_status=board_status):
                output = io.StringIO()
                failure = wire({"jsonrpc": "2.0", "id": 1, "result": {"isError": True, "content": []}})
                client = self.discovery_client({"privateLeaderboard": [], "publicLeaderboard": [], "teams": []},
                                               {}, board_status=board_status, search_raw=failure)
                with mock.patch.object(kaggle, "Client", return_value=client), contextlib.redirect_stdout(output):
                    code = kaggle.main(["discover", "--competition", "wheat", "--question", "representation",
                                        "--output-dir", str(self.output / str(index)), "--format", "source"])
                source = json.loads(output.getvalue())
                self.assertEqual(code, expected_exit)
                self.assertEqual(source["sources"], [])
                self.assertTrue(source["errors"])

    def test_sse_uses_matching_rpc_id_and_does_not_treat_error_words_in_prose_as_failure(self):
        raw = (b"event: message\ndata: " + wire({"jsonrpc": "2.0", "id": 99, "result": {"isError": True}})
               + b"\n\nevent: message\ndata: " + wire(rpc(TOPIC)) + b"\n\n")
        result = kaggle.run(self.args(), self.topic_client(raw=raw))
        self.assertEqual(result["status"], "ok")
        self.assertIn("server error", result["view"]["body"])
        self.assertEqual((Path(result["snapshot"]) / "response-000.bin").read_bytes(), raw)

    def test_bad_json_rpc_tool_errors_and_unsupported_payloads_are_archived_as_failures(self):
        invalid = [
            b"{not-json", b"event: message\ndata: not-json\n\n",
            wire({"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "bad request"}}),
            wire({"jsonrpc": "2.0", "id": 1, "result": {"isError": True, "content": []}}),
            wire({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "not JSON"}]}}),
            wire({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text"}]}}),
            wire(rpc([])),
        ]
        for index, raw in enumerate(invalid):
            with self.subTest(index=index):
                args = self.args()
                args.output_dir = self.output / str(index)
                result = kaggle.run(args, self.topic_client(raw=raw))
                self.assertEqual(result["status"], "error")
                self.assertEqual((Path(result["snapshot"]) / "response-000.bin").read_bytes(), raw)
                self.assertTrue(result["source"]["errors"])

    def test_topic_response_must_identify_requested_topic_and_reject_known_other_competition(self):
        for field, value in (("id", 78), ("url", "/competitions/other/discussion/77")):
            with self.subTest(field=field):
                topic = copy.deepcopy(TOPIC)
                topic["forum_topic"][field] = value
                result = kaggle.run(self.args(), self.topic_client(topic))
                self.assertEqual(result["status"], "error")

    def test_general_topic_keeps_scope_unknown_instead_of_inventing_competition(self):
        topic = copy.deepcopy(TOPIC)
        topic["forum_topic"]["url"] = "/discussions/general/77"
        result = kaggle.run(self.args("--competition", "wheat"), self.topic_client(topic))
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["source"]["competition"])
        self.assertEqual(result["source"]["requested_competition"], "wheat")
        self.assertEqual(result["source"]["competition_verification"], "unknown")

    def test_writeup_keeps_html_body_and_partial_failure_when_linked_comments_cannot_be_read(self):
        writeup = {"id": 51, "slug": "method", "url": "/competitions/wheat/writeups/method",
                   "title": "Method", "message": {"raw_markdown": "", "content": "<p>Complete method</p>"},
                   "topic_id": 77}
        error = wire({"jsonrpc": "2.0", "id": 1, "result": {"isError": True, "content": []}})
        client = self.client(
            mcp_step("get_writeup_by_slug", {"competitionName": "wheat", "slug": "method"}, writeup),
            mcp_step("get_forum_topic", TOPIC_REQUEST, {}, raw=error))
        result = kaggle.run(self.args("--url", "https://www.kaggle.com/competitions/wheat/writeups/method"), client)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["view"]["body"], "Complete method")
        self.assertEqual(result["source"]["errors"][0]["operation"], "writeup_comments")
        self.assertTrue(result["source"]["coverage"]["comments_requested"])
        self.assertIsNone(result["source"]["coverage"]["upstream_complete"])
        self.assertEqual(list(self.output.glob("cache-*.json")), [])

    def test_local_preview_truncates_tree_and_full_reuses_complete_returned_snapshot(self):
        result = kaggle.run(self.args("--comments", "1", "--replies", "1", "--max-chars", "5"), self.topic_client())
        view = result["view"]
        self.assertEqual(view["body"], "Metho")
        self.assertEqual(view["omitted_comments"], 1)
        self.assertEqual(view["comments"][0]["omitted_replies"], 1)
        self.assertEqual(view["comments"][0]["replies"][0]["replies"][0]["body"], "Neste")
        self.assertGreater(view["comments"][0]["omitted_characters"], 0)
        full = kaggle.run(self.args("--full", "--comments", "0", "--replies", "0", "--max-chars", "1"), self.client())
        self.assertTrue(full["cache_hit"])
        self.assertEqual(full["snapshot"], result["snapshot"])
        self.assertEqual(full["view"]["body"], TOPIC["forum_topic"]["first_message"]["raw_markdown"])
        self.assertEqual(full["view"]["omitted_comments"], 0)
        self.assertEqual(full["view"]["comments"][0]["omitted_replies"], 0)
        self.assertEqual(full["view"]["comments"][0]["replies"][0]["replies"][0]["body"], "Nested reply")
        self.assertIn("Second comment", full["view"]["comments"][1]["body"])
        self.assertNotIn("not prose", full["view"]["comments"][1]["body"])
        self.assertIsNone(full["source"]["coverage"]["upstream_complete"])
        self.assertEqual(full["source"]["coverage"]["server_total_messages"], 90)

    def test_partial_comment_placeholders_keep_main_body_reply_tree_and_cache_reading_limits(self):
        topic = copy.deepcopy(TOPIC)
        topic["forum_topic"]["comments"] = [
            {"id": 101, "is_partial": True, "replies": [
                {"id": 111, "raw_markdown": "Correction to the method", "replies": [
                    {"id": 112, "is_partial": True}]}]},
            {"id": 102, "raw_markdown": ""},
        ]
        result = kaggle.run(self.args(), self.topic_client(topic))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["view"]["body"], topic["forum_topic"]["first_message"]["raw_markdown"])
        placeholder = result["view"]["comments"][0]
        self.assertEqual(placeholder["id"], 101)
        self.assertTrue(placeholder["is_partial"])
        self.assertFalse(placeholder["body_available"])
        self.assertEqual(placeholder["body"], "")
        self.assertEqual(placeholder["replies"][0]["body"], "Correction to the method")
        self.assertFalse(placeholder["replies"][0]["replies"][0]["body_available"])
        self.assertTrue(result["view"]["comments"][1]["body_available"])
        coverage = result["source"]["coverage"]
        self.assertEqual(coverage["returned_comment_nodes"], 4)
        self.assertEqual(coverage["returned_comment_bodies"], 2)
        self.assertEqual(coverage["unloaded_comment_bodies"], 2)
        self.assertEqual(coverage["partial_comment_nodes"], 2)
        self.assertIsNone(coverage["upstream_complete"])
        self.assertEqual(Path(result["body_path"]).read_text(), result["view"]["body"])
        full = kaggle.run(self.args("--full"), self.client())
        self.assertTrue(full["cache_hit"])
        self.assertEqual(full["source"]["coverage"], coverage)
        self.assertFalse(full["view"]["comments"][0]["body_available"])

    def test_missing_comment_body_without_partial_marker_remains_an_error(self):
        for partial in (None, False):
            with self.subTest(partial=partial):
                topic = copy.deepcopy(TOPIC)
                topic["forum_topic"]["comments"] = [{"id": 101, "is_partial": partial}]
                result = kaggle.run(self.args(), self.topic_client(topic))
                self.assertEqual(result["status"], "error")
                self.assertIn("no supported message body", result["source"]["errors"][0]["message"])
                self.assertEqual(list(self.output.glob("cache-*.json")), [])

    def test_direct_mode_ignores_proxy_environment_without_changing_it_and_logs_route(self):
        proxy_env = {key: "http://127.0.0.1:27900" for key in (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")}
        with mock.patch.dict(os.environ, proxy_env):
            before = dict(os.environ)
            default = kaggle.Client()
            self.assertTrue(any(isinstance(handler, urllib.request.ProxyHandler) and handler.proxies.get("https")
                                for handler in default.opener.handlers))
            direct = kaggle.Client(direct=True)
            self.assertFalse(any(isinstance(handler, urllib.request.ProxyHandler) and handler.proxies
                                 for handler in direct.opener.handlers))
            self.assertEqual(dict(os.environ), before)
            self.assertTrue(self.args("--direct").direct)
            self.assertTrue(self.args("--direct", command="discover").direct)
            direct.opener = FixedOpener(self, [mcp_step("get_forum_topic", TOPIC_REQUEST, TOPIC)])
            result = kaggle.run(self.args("--direct"), direct)
            self.assertEqual(result["status"], "ok")
            requests = json.loads((Path(result["snapshot"]) / "requests.json").read_bytes())
            self.assertEqual(requests[0]["network_mode"], "direct")
            self.assertEqual(dict(os.environ), before)

    def test_starting_comment_and_page_size_are_forwarded_and_do_not_share_cache_identity(self):
        initial = copy.deepcopy(TOPIC)
        del initial["forum_topic"]["comments"][0]["raw_markdown"]
        initial["forum_topic"]["comments"][0]["is_partial"] = True
        first = kaggle.run(self.args(), self.topic_client(initial))
        self.assertFalse(first["view"]["comments"][0]["body_available"])
        request = {**TOPIC_REQUEST, "startingCommentId": 101, "initialPageSize": 2}
        second = kaggle.run(self.args("--starting-comment-id", "101", "--page-size", "2"),
                            self.topic_client(request=request))
        self.assertFalse(second["cache_hit"])
        self.assertNotEqual(first["snapshot"], second["snapshot"])
        self.assertEqual(second["source"]["coverage"]["request"], request)
        self.assertTrue(second["view"]["comments"][0]["body_available"])
        self.assertEqual(second["view"]["comments"][0]["body"], "First comment with details")
        hit = kaggle.run(self.args(), self.client())
        self.assertTrue(hit["cache_hit"])
        self.assertEqual(hit["snapshot"], first["snapshot"])
        self.assertFalse(hit["view"]["comments"][0]["body_available"])

    def test_failed_refresh_preserves_good_cache_and_original_snapshot_bytes(self):
        original = kaggle.run(self.args(), self.topic_client())
        snapshot = Path(original["snapshot"])
        before = {path.name: path.read_bytes() for path in snapshot.iterdir()}
        index = next(self.output.glob("cache-*.json"))
        cached_before = index.read_bytes()
        refresh = kaggle.run(self.args("--refresh"), self.topic_client(raw=b"upstream unavailable", status=503))
        self.assertEqual(refresh["status"], "error")
        self.assertNotEqual(refresh["snapshot"], original["snapshot"])
        self.assertEqual(index.read_bytes(), cached_before)
        self.assertEqual({path.name: path.read_bytes() for path in snapshot.iterdir()}, before)
        hit = kaggle.run(self.args(), self.client())
        self.assertTrue(hit["cache_hit"])
        self.assertEqual(hit["snapshot"], original["snapshot"])
        self.assertEqual(hit["view"]["body"], original["view"]["body"])

    def test_cached_source_tampering_is_reported_instead_of_becoming_a_new_result(self):
        original = kaggle.run(self.args(), self.topic_client())
        Path(original["source_path"]).write_bytes(b"{}")
        with self.assertRaises(kaggle.SourceError):
            kaggle.run(self.args(), self.client())

    def test_raw_response_and_manifest_bind_exact_bytes_and_do_not_truncate_saved_body(self):
        raw = json.dumps(rpc(TOPIC), ensure_ascii=False, indent=3).encode("utf-8") + b"\r\n"
        result = kaggle.run(self.args("--max-chars", "2"), self.topic_client(raw=raw))
        snapshot = Path(result["snapshot"])
        self.assertEqual((snapshot / "response-000.bin").read_bytes(), raw)
        requests = json.loads((snapshot / "requests.json").read_bytes())
        self.assertEqual(requests[0]["response_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(requests[0]["response_bytes"], len(raw))
        manifest = json.loads((snapshot / "manifest.json").read_bytes())
        self.assertEqual(manifest["sha256"], hashlib.sha256((snapshot / "source.json").read_bytes()).hexdigest())
        self.assertEqual(manifest["response_bytes"], len(raw))
        self.assertEqual(manifest["request_count"], 1)
        self.assertEqual((snapshot / "body.md").read_text(), TOPIC["forum_topic"]["first_message"]["raw_markdown"])

    def test_notebook_explicit_version_binds_kernel_list_number_to_session_not_version_id(self):
        raw = b"print('historical caf\xc3\xa9')\r\n"
        client = self.client(*self.notebook_steps(source=raw))
        result = kaggle.run(self.args("--url", NOTEBOOK_URL, "--version", "2", "--competition", "wheat"), client)
        self.assertEqual(result["status"], "ok")
        source = result["source"]
        self.assertEqual((source["kernel_id"], source["version_number"], source["version_id"], source["script_version_id"]),
                         (501, 2, 9002, 202))
        self.assertTrue(source["url"].endswith("?scriptVersionId=202"))
        self.assertIsNone(source["competition"])
        self.assertEqual(source["requested_competition"], "wheat")
        self.assertEqual(source["competition_verification"], "unknown")
        self.assertEqual(result["view"]["body"], raw.decode())
        self.assertEqual((Path(result["snapshot"]) / "response-003.bin").read_bytes(), raw)
        self.assertEqual(len([path for path, _ in client.opener.calls if path.endswith(kaggle.VIEW)]), 1)

    def test_notebook_url_session_is_checked_against_same_kernel_page_and_page_token_is_forwarded(self):
        client = self.client(*self.notebook_steps(page_token="older"))
        result = kaggle.run(self.args("--url", NOTEBOOK_URL + "?scriptVersionId=202", "--version-page-token", "older"), client)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source"]["version_number"], 2)
        self.assertEqual(result["source"]["coverage"]["version_lookup"]["pageToken"], "older")
        self.assertEqual(result["source"]["coverage"]["next_page_token"], "older-versions")

    def test_read_reuses_exact_notebook_across_run_folders_pins_and_unverified_competition(self):
        old_dir, new_dir = self.output / "old-read", self.output / "new" / "planned-read"
        url = NOTEBOOK_URL + "?scriptVersionId=202"
        body = b"print('decisive historical cell')\r\n"
        first = kaggle.run(self.args("--output-dir", str(old_dir), "--url", url, "--max-chars", "2"),
                           self.client(*self.notebook_steps(source=body)))
        self.assertEqual(first["view"]["body"], "pr")

        for pin in (["--url", url], ["--url", NOTEBOOK_URL, "--version", "2"]):
            with self.subTest(pin=pin), mock.patch.object(kaggle, "Client", side_effect=AssertionError("No client on a hit")):
                recovered = kaggle.run(self.args("--output-dir", str(new_dir), "--cache-root", str(self.output),
                                                 "--competition", "wheat", "--full", *pin))
                self.assertTrue(recovered["cache_hit"])
                for field in ("snapshot", "source_path", "body_path", "sha256", "request_identity", "fetched_at"):
                    self.assertEqual(recovered[field], first[field])
                self.assertEqual(recovered["view"]["body"], body.decode())
                self.assertEqual(Path(recovered["body_path"]).read_bytes(), body)
                self.assertEqual(recovered["source"]["script_version_id"], 202)
                self.assertEqual(recovered["source"]["competition_verification"], "unknown")
                self.assertIsNone(recovered["source"]["competition"])
                self.assertFalse(new_dir.exists())

    def test_cache_only_miss_never_substitutes_other_notebook_versions_or_latest(self):
        old_dir, new_dir = self.output / "old-read", self.output / "not-created"
        kaggle.run(self.args("--output-dir", str(old_dir), "--url", NOTEBOOK_URL, "--version", "2"),
                   self.client(*self.notebook_steps()))
        for target in (["--url", NOTEBOOK_URL, "--version", "3"], ["--url", NOTEBOOK_URL],
                       ["--url", NOTEBOOK_URL + "?scriptVersionId=202", "--version", "3"],
                       ["--url", NOTEBOOK_URL.replace("alice", "bob"), "--script-version-id", "202"]):
            with self.subTest(target=target), mock.patch.object(kaggle, "Client", side_effect=AssertionError("No client in cache-only mode")):
                args = ["read", "--output-dir", str(new_dir), "--cache-root", str(self.output), "--cache-only", *target]
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(kaggle.main(args), 1)
                self.assertIn("No matching successful local source snapshot", json.loads(output.getvalue())["message"])
                self.assertFalse(new_dir.exists())

    def test_source_cache_preserves_topic_range_and_refresh_bypasses_a_match(self):
        old_dir, new_dir = self.output / "old-read", self.output / "new-read"
        first = kaggle.run(self.args("--output-dir", str(old_dir)), self.topic_client())
        lookup = ["--output-dir", str(new_dir), "--cache-root", str(self.output)]
        with mock.patch.object(kaggle, "Client", side_effect=AssertionError("No client on a hit")):
            hit = kaggle.run(self.args(*lookup, "--cache-only", "--full"))
        self.assertTrue(hit["cache_hit"])
        self.assertEqual(hit["body_path"], first["body_path"])
        separate = kaggle.run(self.args(*lookup, "--starting-comment-id", "101"),
                              self.topic_client(request={**TOPIC_REQUEST, "startingCommentId": 101}))
        self.assertFalse(separate["cache_hit"])
        self.assertEqual(separate["source"]["coverage"]["request"]["startingCommentId"], 101)

        refreshed = kaggle.run(self.args(*lookup, "--refresh"), self.topic_client())
        self.assertFalse(refreshed["cache_hit"])
        self.assertNotEqual(refreshed["snapshot"], first["snapshot"])
        self.assertTrue(Path(first["body_path"]).is_file())

    def test_shared_cache_cannot_pass_a_changed_body_as_the_verified_original(self):
        old_dir = self.output / "old-read"
        result = kaggle.run(self.args("--output-dir", str(old_dir)), self.topic_client())
        Path(result["body_path"]).write_text("unbound substitute")
        with self.assertRaisesRegex(kaggle.SourceError, "Cached body bytes changed"):
            kaggle.run(self.args("--output-dir", str(self.output / "new-read"), "--cache-root", str(self.output),
                                "--cache-only"), self.client())

    def test_missing_or_conflicting_notebook_identity_never_fetches_latest_source(self):
        cases = [
            ["--url", NOTEBOOK_URL, "--version", "404"],
            ["--url", NOTEBOOK_URL + "?scriptVersionId=999"],
            ["--url", NOTEBOOK_URL + "?scriptVersionId=303", "--version", "2"],
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                client = self.client(*self.notebook_steps(source=None))
                result = kaggle.run(self.args(*extra), client)
                self.assertEqual(result["status"], "error")
                self.assertIn("no latest fallback", result["source"]["errors"][0]["message"])
                self.assertFalse(any(path.endswith(kaggle.SOURCE) for path, _ in client.opener.calls))

    def test_json_encoded_empty_notebook_source_is_failure(self):
        result = kaggle.run(self.args("--url", NOTEBOOK_URL, "--version", "2"),
                            self.client(*self.notebook_steps(source=b'"   "')))
        self.assertEqual(result["status"], "error")
        self.assertEqual(list(self.output.glob("cache-*.json")), [])

    def test_malformed_version_record_is_saved_as_failure_before_source_download(self):
        rows = [{"version": "unsupported", "run": {"id": 202}}]
        client = self.client(*self.notebook_steps(rows=rows, source=None))
        result = kaggle.run(self.args("--url", NOTEBOOK_URL, "--version", "2"), client)
        self.assertEqual(result["status"], "error")
        snapshot = Path(result["snapshot"])
        self.assertEqual(json.loads((snapshot / "manifest.json").read_bytes())["request_count"], 3)
        self.assertTrue((snapshot / "response-002.bin").is_file())

    def test_cli_input_errors_do_not_make_requests_and_runtime_errors_return_nonzero_json(self):
        invalid = [
            ["--url", "https://example.org/code/alice/wheat-model"],
            ["--version", "2"],
            ["--url", NOTEBOOK_URL + "?scriptVersionId=202", "--script-version-id", "303"],
            ["--competition", "other"],
            ["--version-page-token", "older"],
            ["--url", NOTEBOOK_URL, "--starting-comment-id", "101"],
        ]
        for extra in invalid:
            with self.subTest(extra=extra), mock.patch.object(kaggle, "Client", return_value=self.client()):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = kaggle.main(["read", "--output-dir", str(self.output), "--url", TOPIC_URL] + extra)
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(output.getvalue())["status"], "error")
        for extra in (["--page-size", "0"], ["--comments", "-1"], ["--version", "-1"]):
            with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    self.args(*extra)
                self.assertEqual(raised.exception.code, 2)
        client = self.topic_client(raw=b"service unavailable", status=503)
        output = io.StringIO()
        with mock.patch.object(kaggle, "Client", return_value=client), contextlib.redirect_stdout(output):
            code = kaggle.main(["read", "--output-dir", str(self.output), "--url", TOPIC_URL])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "error")


if __name__ == "__main__":
    unittest.main()
