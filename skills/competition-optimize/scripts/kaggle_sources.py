#!/usr/bin/env python3
"""Read Kaggle research sources without executing or submitting them (stdlib only)."""
from __future__ import annotations

import argparse
import gzip
import hashlib
from html.parser import HTMLParser
import http.client
import http.cookiejar
import json
import os
from pathlib import Path
import re
import socket
import ssl
import time
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request
import zlib


BASE = "https://www.kaggle.com"
VIEW = "kernels.LegacyKernelsService/GetKernelViewModel"
VERSIONS = "kernels.KernelsService/ListKernelVersions"
SOURCE = "kernels.KernelsService/GetKernelSessionSource"


class SourceError(ValueError):
    pass


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def objects(value):
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise SourceError("Expected an array of objects; inspect the saved raw response")
    return value


def mapping(value):
    if not isinstance(value, dict):
        raise SourceError("Expected a JSON object; inspect the saved raw response")
    return value


def absolute(url):
    return urllib.parse.urljoin(BASE + "/", url) if isinstance(url, str) and url else None


def url_competition(url):
    parts = urllib.parse.urlparse(url or "")
    if parts.hostname not in {"www.kaggle.com", "kaggle.com"}:
        return None
    match = re.match(r"/(?:competitions|c)/([^/]+)(?:/|$)", parts.path)
    return match.group(1) if match else None


def competition_slug(value):
    slug = url_competition(value) if "://" in value else value
    if not slug or not re.fullmatch(r"[a-zA-Z0-9_-]+", slug):
        raise SourceError("Use a competition slug or a Kaggle competition URL")
    return slug


def target_url(url, version=None, script_version_id=None):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.kaggle.com", "kaggle.com"}:
        raise SourceError("Use an https Kaggle source URL")
    query = urllib.parse.parse_qs(parsed.query)
    supplied = query.get("scriptVersionId", [])
    if len(supplied) > 1 or (supplied and (number(supplied[0]) or 0) < 1):
        raise SourceError("scriptVersionId must be one positive session ID")
    url_version = number(supplied[0]) if supplied else None
    if script_version_id and url_version and script_version_id != url_version:
        raise SourceError("URL scriptVersionId conflicts with --script-version-id")
    session_id = script_version_id or url_version
    path = parsed.path.rstrip("/")
    canonical = BASE + path
    if match := re.fullmatch(r"/code/([^/]+)/([^/]+)", path):
        return {"kind": "notebook", "url": canonical, "owner": match[1], "slug": match[2],
                "version_number": version, "script_version_id": session_id}
    if version or session_id:
        raise SourceError("Notebook version options require a /code/owner/slug URL")
    if match := re.fullmatch(r"/competitions/([^/]+)/writeups/([^/]+)", path):
        return {"kind": "writeup", "url": canonical, "competition": match[1], "slug": match[2]}
    if match := re.search(r"/discussions?/(?:[^/]+/)?(\d+)$", path):
        return {"kind": "topic", "url": canonical, "topic_id": int(match[1]),
                "competition": url_competition(canonical)}
    raise SourceError("Supported sources: discussion topic, competition writeup, or /code/owner/slug")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if not self.hidden and tag in {"p", "div", "br", "li", "pre", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1
        if not self.hidden and tag in {"p", "div", "li", "pre"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def body_of(message):
    if not isinstance(message, dict):
        raise SourceError("Expected a message object")
    for key in ("raw_markdown", "rawMarkdown", "markdown"):
        if isinstance(message.get(key), str) and message[key]:
            return message[key]
    content = message.get("content")
    if not isinstance(content, str):
        if any(message.get(key) == "" for key in ("raw_markdown", "rawMarkdown", "markdown")):
            return ""
        raise SourceError("Response has no supported message body")
    parser = _Text()
    parser.feed(content)
    return "".join(parser.parts).strip()


def rpc_payload(response):
    if not isinstance(response, dict) or "error" in response:
        raise SourceError("Kaggle JSON-RPC error; inspect the saved raw response")
    result = response.get("result")
    if not isinstance(result, dict) or result.get("isError"):
        raise SourceError("Kaggle tool returned an error or an unsupported response")
    data = result.get("structuredContent")
    if data is None:
        blocks = result.get("content")
        if not isinstance(blocks, list):
            raise SourceError("Kaggle tool response has no content array")
        texts = [item["text"] for item in blocks if isinstance(item, dict) and item.get("type") == "text"
                 and isinstance(item.get("text"), str)]
        try:
            data = json.loads("\n".join(texts))
        except (ValueError, TypeError) as exc:
            raise SourceError("Tool body is not JSON; inspect the saved raw response") from exc
    if not isinstance(data, dict):
        raise SourceError("Expected a JSON object in the Kaggle tool response")
    return data


def parse_rpc(raw):
    try:
        if raw.lstrip().startswith(("event:", "data:")):
            messages = [json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith("data:")]
            response = next((m for m in messages if isinstance(m, dict) and m.get("id") == 1), None)
        else:
            response = json.loads(raw)
    except ValueError as exc:
        raise SourceError("Invalid JSON/SSE response") from exc
    return rpc_payload(response)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _connect_with_mss(address, timeout, source_address=None, *, tcp_mss):
    last_error = None
    for family, kind, protocol, _, target in socket.getaddrinfo(*address, type=socket.SOCK_STREAM):
        connection = socket.socket(family, kind, protocol)
        try:
            connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG, tcp_mss)
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                connection.settimeout(timeout)
            if source_address:
                connection.bind(source_address)
            connection.connect(target)
            return connection
        except OSError as exc:
            last_error = exc
            connection.close()
    raise last_error or OSError("No addresses returned for Kaggle")


class _MSSHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, tcp_mss):
        super().__init__()
        self.tcp_mss = tcp_mss

    def https_open(self, request):
        def connection(*args, **kwargs):
            result = http.client.HTTPSConnection(*args, **kwargs)
            result._create_connection = lambda address, timeout, source_address=None: _connect_with_mss(
                address, timeout, source_address, tcp_mss=self.tcp_mss)
            return result
        return self.do_open(connection, request, context=self._context)


class Client:
    """Fixed Kaggle read endpoints; request logs never contain authorization headers."""
    def __init__(self, timeout=30, *, direct=False, retries=2, tcp_mss=None):
        self.timeout, self.requests, self.responses = timeout, [], []
        self.retries = retries
        self.tcp_mss = tcp_mss
        self.network_mode = "direct" if direct else "environment"
        self.cookies = http.cookiejar.CookieJar()
        handlers = [urllib.request.HTTPCookieProcessor(self.cookies), _NoRedirect()]
        if direct:
            handlers.append(urllib.request.ProxyHandler({}))
        if tcp_mss is not None:
            if not hasattr(socket, "TCP_MAXSEG"):
                raise SourceError("--tcp-mss is not supported on this platform")
            handlers.append(_MSSHTTPSHandler(tcp_mss))
        self.opener = urllib.request.build_opener(*handlers)
        self.token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
        if not self.token:
            token_path = Path(os.environ.get("KAGGLE_CONFIG_DIR") or Path.home() / ".kaggle") / "access_token"
            if token_path.is_file():
                self.token = token_path.read_text(encoding="utf-8").strip()
        self.web_initialized = False

    def request(self, path, payload=None):
        for attempt in range(self.retries + 1):
            headers = {"Accept": "application/json, text/event-stream", "Accept-Encoding": "gzip",
                       "User-Agent": "competition-optimize-sources/1"}
            if self.token:
                headers["Authorization"] = "Bearer " + self.token
            if payload is not None:
                headers["Content-Type"] = "application/json"
            for cookie in self.cookies:
                if cookie.name == "XSRF-TOKEN":
                    headers["X-XSRF-TOKEN"] = urllib.parse.unquote(cookie.value)
            request = urllib.request.Request(BASE + path, data=encoded(payload) if payload is not None else None, headers=headers)
            entry = {"path": path, "payload": payload, "network_mode": self.network_mode,
                     "tcp_mss": self.tcp_mss,
                     "attempt": attempt + 1, "status": None, "response_complete": False,
                     "fetched_at": datetime.now(timezone.utc).isoformat()}
            started, raw, retryable = time.monotonic(), bytearray(), False
            try:
                try:
                    response = self.opener.open(request, timeout=self.timeout)
                except urllib.error.HTTPError as exc:
                    response = exc
                with response:
                    entry.update(status=response.status, content_type=response.headers.get("Content-Type"),
                                 content_encoding=response.headers.get("Content-Encoding"))
                    while chunk := response.read1(65536):
                        raw.extend(chunk)
                    if remaining := getattr(response, "length", None):
                        raise http.client.IncompleteRead(b"", remaining)
                    entry["response_complete"] = True
            except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
                if isinstance(exc, http.client.IncompleteRead):
                    raw.extend(exc.partial)
                entry["error"] = str(exc)
                reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
                retryable = (entry["status"] in (None, 200)
                             and not isinstance(reason, ssl.SSLCertVerificationError))
            raw = bytes(raw)
            entry.update(response_file=f"response-{len(self.requests):03d}.bin", response_sha256=digest(raw), response_bytes=len(raw))
            entry["seconds"] = time.monotonic() - started
            self.requests.append(entry)
            self.responses.append(raw)
            if retryable and attempt < self.retries:
                time.sleep(min(2 ** attempt, 4))
                continue
            if entry.get("error"):
                raise SourceError(f"Kaggle {path}: network request failed after {attempt + 1} attempt(s)")
            if entry["status"] != 200:
                raise SourceError(f"Kaggle {path}: HTTP {entry['status']}")
            try:
                if entry["content_encoding"] == "gzip":
                    raw = gzip.decompress(raw)
                elif entry["content_encoding"] not in (None, "", "identity"):
                    raise SourceError("Unsupported Kaggle response encoding; inspect saved raw response")
            except (OSError, EOFError, zlib.error) as exc:
                raise SourceError("Invalid compressed Kaggle response; inspect saved raw response") from exc
            entry["decoded_bytes"] = len(raw)
            return raw.decode("utf-8", errors="replace")

    def mcp(self, tool, request):
        return parse_rpc(self.request("/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                              "params": {"name": tool, "arguments": {"request": request}}}))

    def web(self, endpoint, request, *, text=False):
        if not self.web_initialized:
            self.web_initialized = True
            try:
                self.request("/")
            except SourceError:
                pass  # The endpoint may still answer without an XSRF cookie.
        raw = self.request("/api/i/" + endpoint, request)
        if raw.lstrip().lower().startswith(("<!doctype html", "<html")):
            raise SourceError("Kaggle returned HTML instead of source/JSON")
        if text:
            return raw
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise SourceError("Kaggle web response is not JSON") from exc
        if not isinstance(data, dict) or "error" in data:
            raise SourceError("Kaggle web response is not a successful JSON object")
        return data


def identity(url, expected=None):
    actual = url_competition(url)
    if expected and actual and expected != actual:
        raise SourceError(f"Source belongs to {actual}, not requested competition {expected}")
    return {"competition": actual, "requested_competition": expected,
            "competition_verification": "returned_url" if actual else "unknown"}


def message(row):
    author = row.get("author") or {}
    partial = row.get("is_partial") is True
    body_available = any(isinstance(row.get(key), str) for key in ("raw_markdown", "rawMarkdown", "markdown", "content"))
    return {"id": row.get("id"), "author": author.get("display_name") if isinstance(author, dict) else author,
            "posted": row.get("post_date"), "is_partial": partial, "body_available": body_available,
            "body": "" if partial and not body_available else body_of(row),
            "replies": [message(reply) for reply in objects(row.get("replies", []))]}


def message_tree(rows):
    for row in rows:
        yield row
        yield from message_tree(row["replies"])


def read_topic(client, target, args):
    request = {"forumTopicId": target["topic_id"], "includeComments": True, "initialPageSize": args.page_size}
    if args.starting_comment_id:
        request["startingCommentId"] = args.starting_comment_id
    data = client.mcp("get_forum_topic", request)
    topic = data.get("forum_topic")
    if not isinstance(topic, dict) or number(topic.get("id")) != target["topic_id"]:
        raise SourceError("Topic response does not identify the requested topic")
    url = absolute(topic.get("url"))
    comments = [message(row) for row in objects(topic.get("comments", []))]
    nodes = list(message_tree(comments))
    available = sum(row["body_available"] for row in nodes)
    source = {"kind": "topic", "id": topic["id"], "url": url, "title": topic.get("name"),
              **identity(url, args.competition or target.get("competition")),
              "body": body_of(topic.get("first_message") or {}),
              "comments": comments,
              "coverage": {"server_total_messages": number(topic.get("total_messages")),
                           "returned_comment_nodes": len(nodes), "returned_comment_bodies": available,
                           "unloaded_comment_bodies": len(nodes) - available,
                           "partial_comment_nodes": sum(row["is_partial"] for row in nodes),
                           "comments_requested": True,
                           "comments_field_returned": "comments" in topic,
                           "upstream_complete": None, "request": request,
                           "note": "Counts describe the returned tree, not all historical comments."}}
    return source


def read_writeup(client, target, args):
    data = client.mcp("get_writeup_by_slug", {"competitionName": target["competition"], "slug": target["slug"]})
    if not data.get("id") or data.get("slug") != target["slug"]:
        raise SourceError("Writeup response does not identify the requested writeup")
    url = absolute(data.get("url"))
    source = {"kind": "writeup", "id": data["id"], "url": url, "title": data.get("title"),
              **identity(url, args.competition or target["competition"]),
              "body": body_of(data.get("message") or {}), "comments": [],
              "topic_id": number(data.get("topic_id")), "links": data.get("write_up_links", []),
              "coverage": {"upstream_complete": None, "comments_requested": False}}
    if source["topic_id"]:
        source["coverage"]["comments_requested"] = True
        try:
            topic = read_topic(client, {"topic_id": source["topic_id"], "competition": target["competition"]}, args)
            source.update(comments=topic["comments"], coverage=topic["coverage"])
        except SourceError as exc:
            source["errors"] = [{"operation": "writeup_comments", "message": str(exc)}]
    return source


def read_notebook(client, target, args):
    view = client.web(VIEW, {"authorUserName": target["owner"], "kernelSlug": target["slug"], "tab": "output"})
    kernel = mapping(view.get("kernel"))
    kernel_id = number(kernel.get("id"))
    if not kernel_id:
        raise SourceError("Notebook view does not expose its kernel ID")
    # One kernel-scoped metadata page; never score/rank every historical version.
    request = {"kernelId": kernel_id, "sortOption": "VERSION_ID", "pageSize": args.page_size}
    if args.version_page_token:
        request["pageToken"] = args.version_page_token
    listing = client.web(VERSIONS, request)
    rows = []
    for item in objects(listing.get("items")):
        version, run = mapping(item.get("version", {})), mapping(item.get("run", {}))
        if number(version.get("versionNumber")) and number(run.get("id")):
            rows.append({"version_number": number(version["versionNumber"]), "script_version_id": number(run["id"]),
                         "version_id": version.get("id"), "title": run.get("title")})
    desired_number, desired_session = target["version_number"], target["script_version_id"]
    if not desired_number and not desired_session:
        desired_session = number(mapping(view.get("kernelRun", {})).get("id"))
        if not desired_session:
            raise SourceError("Cannot identify the latest notebook session; no source substituted")
    selected = next((row for row in rows if (not desired_number or row["version_number"] == desired_number)
                     and (not desired_session or row["script_version_id"] == desired_session)), None)
    if selected is None:
        raise SourceError("Requested version/session not verified in this kernel's returned version page; "
                          f"no latest fallback. nextPageToken={listing.get('nextPageToken')!r}; inspect raw response")
    raw = client.web(SOURCE, {"kernelSessionId": selected["script_version_id"], "includeOutputIfAvailable": False}, text=True)
    if not raw.strip():
        raise SourceError("Notebook source was empty")
    # Some services JSON-encode a source string; the raw response remains saved.
    try:
        notebook = json.loads(raw)
    except ValueError:
        notebook = None
    if isinstance(notebook, str):
        raw = notebook
    elif isinstance(notebook, dict) and ("error" in notebook or notebook.get("isError")):
        raise SourceError("Notebook source endpoint returned an error object")
    if not raw.strip():
        raise SourceError("Decoded notebook source was empty")
    return {"kind": "notebook", "url": target["url"] + "?scriptVersionId=" + str(selected["script_version_id"]),
            "title": selected["title"], "kernel_id": kernel_id, **selected, **identity(None, args.competition),
            "body": raw, "comments": [],
            "requested_version_number": target["version_number"], "requested_script_version_id": target["script_version_id"],
            "coverage": {"version_lookup": request, "next_page_token": listing.get("nextPageToken"),
                         "version_identity_basis": "kernel-scoped ListKernelVersions record", "outputs_requested": False}}


def board_writeups(data):
    if "privateLeaderboard" not in data and "publicLeaderboard" not in data:
        raise SourceError("Leaderboard response has no supported board array")
    board = "private" if data.get("privateLeaderboard") else "public"
    ranks = {str(row.get("teamId")): row for row in objects(data.get(board + "Leaderboard", []))}
    found = []
    for team in objects(data.get("teams", [])):
        url = absolute(team.get("solutionWriteUpUrl") or team.get("solutionWriteupUrl"))
        rank = ranks.get(str(team.get("teamId")))
        if url and rank is not None:
            found.append({"url": url, "team_id": team["teamId"], "team_name": team.get("teamName"),
                          "rank": number(rank.get("rank") or rank.get(board + "LeaderboardRank")),
                          "score": next((rank[key] for key in ("score", "displayScore", board + "Score") if rank.get(key) is not None), None),
                          "board": board, "discovered_by": "leaderboard_team_join"})
    return sorted(found, key=lambda row: (row["rank"] is None, row["rank"] or 0))


def discover(client, args):
    slug = args.competition
    facts = client.web("competitions.CompetitionService/GetCompetition", {"competitionName": slug})
    comp = facts.get("competition", facts)
    if not isinstance(comp, dict):
        raise SourceError("Competition response has no competition object")
    comp_id = number(comp.get("id") or comp.get("competitionId"))
    returned_url = absolute(comp.get("url"))
    if returned_url:
        identity(returned_url, slug)
    returned_slug = comp.get("competitionName") or comp.get("slug")
    if returned_slug and returned_slug != slug:
        raise SourceError("Returned competition slug differs from the requested competition")
    if not comp_id:
        raise SourceError("Competition response has no numeric ID; search scope cannot be established")
    found, errors, quantities = [], [], []
    def count(value, name, entity, unit, scope, location, method):
        # Bind counts to the response population before callers summarize them.
        # The last request is the successful web/tool response just decoded.
        response = client.requests[-1]
        quantities.append({"name": name, "value": value, "entity": entity, "unit": unit,
                           "scope": {"competition": slug, **scope},
                           "basis": {"response_file": response["response_file"],
                                     "response_sha256": response["response_sha256"],
                                     "location": location, "method": method}})
    forum_id = number(comp.get("forumId"))
    search_coverage = {"search_forum_id": forum_id, "search_page": args.search_page,
                       "returned_search_topics": 0, "server_search_count": None}
    try:
        board = client.web("competitions.LeaderboardService/GetLeaderboard", {"competitionId": comp_id})
        leads = board_writeups(board)
        selected = "private" if board.get("privateLeaderboard") else "public"
        field = selected + "Leaderboard"
        if field in board:
            count(len(board[field]), "returned_leaderboard_entries", "leaderboard_entry", "entries",
                  {"board": selected, "population": "returned_response"}, "/" + field, "array_length")
        for lead in leads:
            actual = url_competition(lead["url"])
            if actual and actual != slug:
                errors.append({"operation": "leaderboard_identity", "url": lead["url"], "message": "Other competition excluded"})
            else:
                found.append({**lead, "competition": actual,
                              "competition_verification": "returned_url" if actual else "leaderboard_link_only"})
    except SourceError as exc:
        errors.append({"operation": "leaderboard", "message": str(exc)})
    try:
        if not forum_id:
            raise SourceError("Competition response has no forum ID; scoped forum search was not attempted")
        data = client.mcp("list_forum_topics", {
            "forumId": forum_id, "hasForumId": True, "searchQuery": args.question, "hasSearchQuery": True,
            "sortBy": "Relevance", "page": args.search_page, "category": "Competitions", "group": "All"})
        # The live service returns {} for a valid empty search.
        if "topics" not in data and data and number(data.get("count")) != 0:
            raise SourceError("Forum search response has no supported topic array")
        topics = objects(data.get("topics", []))
        search_coverage.update(returned_search_topics=len(topics), server_search_count=number(data.get("count")))
        scope = {"forum_id": forum_id, "query": args.question, "page": args.search_page,
                 "population": "returned_response"}
        if "topics" in data:
            count(len(topics), "returned_search_topics", "forum_topic", "topics", scope,
                  "parsed tool result /topics", "array_length")
        if search_coverage["server_search_count"] is not None:
            count(search_coverage["server_search_count"], "server_search_matches", "forum_topic", "topics",
                  {**scope, "population": "server_reported_query_matches"},
                  "parsed tool result /count", "server_reported")
        for doc in topics:
            url, parent = absolute(doc.get("topic_url")), absolute(doc.get("parent_url"))
            actual, parent_competition = url_competition(url), url_competition(parent)
            if any(value and value != slug for value in (actual, parent_competition)):
                errors.append({"operation": "search_identity", "url": url, "message": "Other competition excluded"})
                continue
            if url:
                found.append({"url": url, "title": doc.get("title"), "rank": None, "board": None,
                              "topic_id": number(doc.get("id")), "parent_url": parent,
                              "discovered_by": "forum-search", "competition": actual or parent_competition,
                              "competition_verification": "returned_url" if actual else
                                  "returned_parent_url" if parent_competition else "request_filter_only"})
    except SourceError as exc:
        errors.append({"operation": "forum_search", "message": str(exc)})
    return {"kind": "discovery", "url": returned_url, "requested_competition": slug,
            "competition": url_competition(returned_url) or returned_slug, "competition_id": comp_id,
            "competition_identity_basis": "GetCompetition response to exact competitionName request",
            "question": args.question, "title": comp.get("title"), "body": "", "comments": [],
            "sources": found, "errors": errors, "quantities": quantities,
            "coverage": {**search_coverage, "upstream_complete": None,
                         "note": "These are leads from the returned board and one search response, not full recall."}}


def source_summary(source, args):
    result = {key: value for key, value in source.items() if key not in {"body", "comments"}}
    if source["kind"] == "discovery" and "sources" in source:
        board = [row for row in source["sources"] if row["discovered_by"] != "forum-search"]
        search = [row for row in source["sources"] if row["discovered_by"] == "forum-search"]
        shown = search[:args.page_size]
        result["sources"] = board + shown
        result["coverage"] = {**source["coverage"], "search_display_limit": args.page_size,
                              "displayed_search_topics": len(shown), "omitted_search_topics": len(search) - len(shown)}
    return result


def preview(source, args):
    maximum = 0 if args.full else args.max_chars
    def item(row):
        text = row["body"]
        result = {key: value for key, value in row.items() if key not in {"body", "replies"}}
        result.update(body=text[:maximum] if maximum else text, omitted_characters=max(len(text) - maximum, 0) if maximum else 0)
        children = row.get("replies", [])
        shown = children if args.full else children[:args.replies]
        result.update(replies=[item(child) for child in shown], returned_replies=len(children), omitted_replies=len(children)-len(shown))
        return result
    rows = source.get("comments", [])
    shown = rows if args.full else rows[:args.comments]
    return {"body": source.get("body", "")[:maximum] if maximum else source.get("body", ""),
            "omitted_body_characters": max(len(source.get("body", "")) - maximum, 0) if maximum else 0,
            "comments": [item(row) for row in shown], "returned_comments": len(rows), "omitted_comments": len(rows)-len(shown)}


def run(args, client=None):
    client = client or Client(args.timeout, direct=args.direct, retries=args.retries, tcp_mss=args.tcp_mss)
    if args.command == "discover":
        args.competition = competition_slug(args.competition)
        target = {"kind": "discovery", "competition": args.competition, "question": args.question}
    else:
        target = target_url(args.url, args.version, args.script_version_id)
        if args.competition:
            args.competition = competition_slug(args.competition)
        if target.get("competition") and args.competition and target["competition"] != args.competition:
            raise SourceError("Source URL conflicts with --competition")
        if args.starting_comment_id and target["kind"] == "notebook":
            raise SourceError("--starting-comment-id applies only to topics/writeups")
        if args.version_page_token and target["kind"] != "notebook":
            raise SourceError("--version-page-token applies only to notebooks")
    key = {"target": target, "competition": args.competition,
           "page_size": args.page_size if args.command == "read" else None,
           "starting_comment_id": args.starting_comment_id, "version_page_token": args.version_page_token}
    if args.command == "discover":
        key["search_page"] = args.search_page
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    key_hash = digest(encoded(key))
    cache = output / ("cache-" + key_hash + ".json")
    if cache.exists() and not args.refresh:
        saved = json.loads(cache.read_text())
        snapshot = Path(saved["snapshot"])
        raw = (snapshot / "source.json").read_bytes()
        if digest(raw) != saved["sha256"]:
            raise SourceError("Cached source bytes changed; inspect or explicitly refresh")
        source = json.loads(raw)
        return {**saved, "cache_hit": True, "source": source_summary(source, args),
                "view": preview(source, args)}
    snapshot = output / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + key_hash[:12])
    snapshot.mkdir()
    try:
        if args.command == "discover":
            source = discover(client, args)
        else:
            source = {"topic": read_topic, "writeup": read_writeup, "notebook": read_notebook}[target["kind"]](client, target, args)
        status = "partial" if source.get("errors") else "ok"
        if source["kind"] == "discovery" and len(source.get("errors", [])) >= 2 and not source["sources"]:
            status = "error"
    except SourceError as exc:
        source, status = {"kind": target["kind"], "body": "", "comments": [], "errors": [{"message": str(exc)}]}, "error"
    source_raw = encoded(source)
    (snapshot / "source.json").write_bytes(source_raw)
    (snapshot / "body.md").write_text(source.get("body", ""))
    (snapshot / "requests.json").write_bytes(encoded(client.requests))
    for entry, raw in zip(client.requests, client.responses):
        (snapshot / entry["response_file"]).write_bytes(raw)
    manifest = {"status": status, "snapshot": str(snapshot), "source_path": str(snapshot / "source.json"),
                "body_path": str(snapshot / "body.md"), "sha256": digest(source_raw), "request_identity": key,
                "fetched_at": datetime.now(timezone.utc).isoformat(), "request_count": len(client.requests),
                "request_seconds": sum(row.get("seconds", 0) for row in client.requests),
                "response_bytes": sum(row.get("response_bytes", 0) for row in client.requests)}
    (snapshot / "manifest.json").write_bytes(encoded(manifest))
    if status == "ok":
        cache.write_bytes(encoded(manifest))  # Partial/failed refreshes never replace a usable cache.
    return {**manifest, "cache_hit": False, "source": source_summary(source, args),
            "view": preview(source, args)}


def positive(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return result


def nonnegative(value):
    result = int(value)
    if result < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("discover", "read"):
        cli = sub.add_parser(command)
        cli.add_argument("--output-dir", type=Path, required=True)
        cli.add_argument("--competition", required=command == "discover")
        cli.add_argument("--page-size", type=positive, default=20 if command == "discover" else 200,
                         help="Local search-lead display limit" if command == "discover" else "Requested comment/version page size")
        cli.add_argument("--refresh", action="store_true")
        cli.add_argument("--format", choices=("json", "source"), default="json",
                         help="json: status, paths, source summary and view; source: full normalized source at the JSON root")
        cli.add_argument("--timeout", type=positive, default=30)
        cli.add_argument("--retries", type=nonnegative, default=2, help="Additional attempts after transport failures; HTTP/tool errors are not retried")
        cli.add_argument("--tcp-mss", type=positive, help="Set TCP maximum segment size for this command's connections (platform dependent)")
        cli.add_argument("--direct", action="store_true", help="Ignore proxy environment settings for this command")
        cli.set_defaults(starting_comment_id=None, version_page_token=None, full=False, max_chars=8000, comments=3, replies=2)
        if command == "discover":
            cli.add_argument("--question", required=True)
            cli.add_argument("--search-page", type=positive, default=1, help="Explicit forum search page")
        else:
            cli.add_argument("--url", required=True)
            cli.add_argument("--version", type=positive, help="Notebook version NUMBER, not scriptVersionId")
            cli.add_argument("--script-version-id", type=positive, help="Notebook session ID, as in the URL")
            cli.add_argument("--version-page-token")
            cli.add_argument("--starting-comment-id", type=positive)
            cli.add_argument("--comments", type=nonnegative, default=3)
            cli.add_argument("--replies", type=nonnegative, default=2)
            cli.add_argument("--max-chars", type=nonnegative, default=8000, help="Per message; 0 removes local character truncation")
            cli.add_argument("--full", action="store_true", help="Show the full returned body/comment tree; no claim of full upstream history")
    return parser.parse_args(argv)


def main(argv=None):
    try:
        args = parse_args(argv)
        result = run(args)
        # A consumer that needs sources/coverage can request the normalized
        # document directly, without recreating an envelope parser. Keep the
        # default output and successful cache identity backward compatible.
        output = (json.loads(Path(result["source_path"]).read_bytes())
                  if args.format == "source" else result)
    except (SourceError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
