#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


POST_RE = re.compile(r"^_posts/\d{4}-\d{2}-\d{2}-(?P<slug>.+)\.md$")


def run_git(args):
    return subprocess.check_output(["git", *args], text=True).strip()


def changed_posts():
    before = os.environ.get("GITHUB_EVENT_BEFORE", "")
    after = os.environ.get("GITHUB_SHA", "")

    if not after:
        return []

    if not before or set(before) == {"0"}:
        output = run_git(["show", "--name-status", "--format=", after, "--", "_posts"])
    else:
        output = run_git(["diff", "--name-status", before, after, "--", "_posts"])

    posts = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        path = parts[-1]
        if status != "A":
            continue
        if POST_RE.match(path):
            posts.append(path)
    return posts


def parse_front_matter(path):
    text = Path(path).read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}

    end = text.find("\n---", 3)
    if end == -1:
        return {}

    meta = {}
    for line in text[3:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        meta[key] = value
    return meta


def post_url(path):
    match = POST_RE.match(path)
    if not match:
        raise ValueError(f"invalid post path: {path}")

    return f"/posts/{match.group('slug')}/"


def notify(endpoint, token, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")
        return response.status, body


def main():
    token = os.environ.get("SUBSCRIBE_NOTIFY_TOKEN")
    endpoint = os.environ.get("SUBSCRIBE_NOTIFY_ENDPOINT", "https://comments.masanam.co.kr/api/subscribers/notify")

    if not token:
        print("SUBSCRIBE_NOTIFY_TOKEN is not set; skipping subscriber notification.")
        return 0

    posts = changed_posts()
    if not posts:
        print("No changed posts to notify.")
        return 0

    seen = set()
    for path in posts:
        if path in seen:
            continue
        seen.add(path)

        meta = parse_front_matter(path)
        title = meta.get("title") or Path(path).stem
        summary = meta.get("description") or ""
        payload = {
            "title": title,
            "url": post_url(path),
            "summary": summary,
        }

        try:
            code, body = notify(endpoint, token, payload)
        except urllib.error.HTTPError as exc:
            print(f"Failed to notify {path}: HTTP {exc.code} {exc.read().decode('utf-8', 'replace')}", file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"Failed to notify {path}: {exc}", file=sys.stderr)
            return 1

        print(f"Notified {path}: HTTP {code} {body}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
