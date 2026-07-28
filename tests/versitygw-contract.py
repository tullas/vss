#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import os
import urllib.error
import urllib.parse
import urllib.request

REGION = "us-east-1"
SERVICE = "s3"
BUCKET = "vss-contract-security-foundation"
OBJECT = "persistence/check.txt"
PAYLOAD = b"vss-versitygw-persistence-check\n"


def signature_key(secret: str, date: str) -> bytes:
    key_date = hmac.new(("AWS4" + secret).encode(), date.encode(), hashlib.sha256).digest()
    key_region = hmac.new(key_date, REGION.encode(), hashlib.sha256).digest()
    key_service = hmac.new(key_region, SERVICE.encode(), hashlib.sha256).digest()
    return hmac.new(key_service, b"aws4_request", hashlib.sha256).digest()


def request(endpoint: str, access: str, secret: str, method: str, path: str, query: str = "", body: bytes = b"") -> tuple[int, bytes]:
    now = dt.datetime.now(dt.timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")
    parsed = urllib.parse.urlsplit(endpoint)
    canonical_uri = urllib.parse.quote(path, safe="/-_.~")
    canonical_query = urllib.parse.urlencode(sorted(urllib.parse.parse_qsl(query, keep_blank_values=True)))
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical_headers = f"host:{parsed.netloc}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{timestamp}\n"
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join((method, canonical_uri, canonical_query, canonical_headers, signed_headers, payload_hash))
    scope = f"{date}/{REGION}/{SERVICE}/aws4_request"
    string_to_sign = "\n".join(("AWS4-HMAC-SHA256", timestamp, scope, hashlib.sha256(canonical_request.encode()).hexdigest()))
    signature = hmac.new(signature_key(secret, date), string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = f"AWS4-HMAC-SHA256 Credential={access}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"
    url = endpoint.rstrip("/") + canonical_uri + ("?" + canonical_query if canonical_query else "")
    http_request = urllib.request.Request(url, data=body if method in {"PUT", "POST"} else None, method=method)
    http_request.add_header("Authorization", authorization)
    http_request.add_header("x-amz-content-sha256", payload_hash)
    http_request.add_header("x-amz-date", timestamp)
    try:
        with urllib.request.urlopen(http_request, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def require(status: int, expected: set[int], check: str) -> None:
    if status not in expected:
        raise RuntimeError(f"{check} failed with HTTP {status}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("seed", "verify-cleanup"))
    parser.add_argument("--endpoint", default="http://127.0.0.1:9000")
    args = parser.parse_args()
    access = os.environ.get("VSS_CONTRACT_ACCESS_KEY")
    secret = os.environ.get("VSS_CONTRACT_SECRET_KEY")
    if not access or not secret:
        parser.error("contract credentials must be provided through the protected environment")

    if args.phase == "seed":
        status, _ = request(args.endpoint, access, secret, "PUT", f"/{BUCKET}")
        require(status, {200}, "create bucket")
        status, _ = request(args.endpoint, access, secret, "PUT", f"/{BUCKET}/{OBJECT}", body=PAYLOAD)
        require(status, {200}, "put object")
        print("VersityGW contract seed passed")
        return 0

    status, body = request(args.endpoint, access, secret, "GET", f"/{BUCKET}/{OBJECT}")
    require(status, {200}, "get object")
    if body != PAYLOAD:
        raise RuntimeError("get object returned unexpected content")
    status, _ = request(args.endpoint, access, secret, "HEAD", f"/{BUCKET}/{OBJECT}")
    require(status, {200}, "head object")
    status, body = request(args.endpoint, access, secret, "GET", f"/{BUCKET}", "list-type=2")
    require(status, {200}, "list objects")
    if OBJECT.encode() not in body:
        raise RuntimeError("list objects omitted expected key")
    status, _ = request(args.endpoint, access, secret, "DELETE", f"/{BUCKET}/{OBJECT}")
    require(status, {204}, "delete object")
    status, _ = request(args.endpoint, access, secret, "DELETE", f"/{BUCKET}")
    require(status, {204}, "delete bucket")
    print("VersityGW persistence and contract verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
