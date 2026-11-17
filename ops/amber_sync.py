#!/usr/bin/env python3
"""Fail-closed public Release mirror. Python 3.12+, standard library only.

All mutations (including operator commands) share one lock. There is deliberately
no permanent-delete operation. Runtime state and downloads never belong in Git.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

PRODUCTS = {"AMBER": "ayr1k/amber-launcher", "AmberE": "ayr1k/AmberE"}
WEBSITE = "ayr1k/ayr1k.github.io"
VERSION = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]*\Z")
INSTALLER = re.compile(
    r"(?:Setup-(?:x64|arm64|ia32)\.(?:exe|msi)|"
    r"windows-(?:x64|arm64|ia32)\.zip|"
    r"mac-(?:x64|arm64|universal)\.(?:zip|dmg|pkg)|"
    r"linux-(?:x64|arm64)\.(?:deb|rpm|AppImage|tar\.gz)|"
    r"freebsd-(?:x64|arm64)-experimental\.tar\.gz)\Z")
ARCHIVE = re.compile(r"\.(?:exe|msi|zip|deb|rpm|AppImage|dmg|pkg|tar\.gz)\Z")


class SyncError(Exception):
    """Messages are fixed operational codes: no server response or signed URL."""


def require(condition, message):
    if not condition:
        raise SyncError(message)


def key(version):
    require(isinstance(version, str) and VERSION.fullmatch(version), "INVALID_VERSION")
    return tuple(map(int, version.split(".")))


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(path):
    require(path.is_file() and not path.is_symlink(), "NOT_REGULAR_FILE")
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def confined(root: Path, relative: str) -> Path:
    """Reject symlinks even when their resolved target remains inside root."""
    require(not root.is_symlink() and root.is_absolute(), "UNSAFE_ROOT")
    parts = Path(relative).parts
    require(parts and not Path(relative).is_absolute() and
            all(p not in (".", "..", "") for p in parts), "UNSAFE_PATH")
    target = root
    for part in parts:
        target = target / part
        require(not target.is_symlink(), "SYMLINK_REFUSED")
    require(target.resolve().is_relative_to(root.resolve()), "PATH_ESCAPE")
    return target


def sync_dir(path):
    if os.name != "nt":
        fd = os.open(path, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def sync_tree(path):
    for file in path.rglob("*"):
        require(not file.is_symlink(), "STAGING_SYMLINK")
        if file.is_file():
            with file.open("r+b" if os.name == "nt" else "rb") as handle:
                os.fsync(handle.fileno())
    for directory in sorted((p for p in path.rglob("*") if p.is_dir()), reverse=True):
        sync_dir(directory)
    sync_dir(path)


def atomic_json(path, value, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temp.open("xb") as handle:
        handle.write(encoded(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    temp.chmod(mode)
    os.replace(temp, path)
    sync_dir(path.parent)


def log(event, **fields):
    print(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "event": event, **fields}, sort_keys=True), flush=True)


@contextlib.contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.is_symlink(), "LOCK_SYMLINK")
    with path.open("a+b") as handle:
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                if not handle.read(1):
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SyncError("ALREADY_RUNNING") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def trusted_url(url):
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == "https" and parsed.port in (None, 443) and
            not parsed.username and not parsed.password and parsed.hostname in {
                "api.github.com", "github.com", "codeload.github.com",
                "release-assets.githubusercontent.com", "objects.githubusercontent.com",
                "github-releases.githubusercontent.com"}, "UNTRUSTED_DOWNLOAD_HOST")
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        trusted_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class GitHub:
    def __init__(self, cache):
        self.cache = cache
        # Public repos need no token. No proxy credentials or user netrc involved.
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}), SafeRedirect())

    def open(self, url, headers=None):
        trusted_url(url)
        for attempt in range(3):
            try:
                return self.http.open(urllib.request.Request(url, headers={
                    "User-Agent": "AMBER-public-mirror/1", **(headers or {})}), timeout=30)
            except urllib.error.HTTPError as exc:
                if exc.code == 304:
                    raise
                if exc.code in (403, 429):
                    raise SyncError("GITHUB_RATE_LIMIT_OR_FORBIDDEN") from None
                if exc.code not in (500, 502, 503, 504):
                    raise SyncError("GITHUB_HTTP_" + str(exc.code)) from None
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
            if attempt < 2:
                time.sleep(2 ** attempt)
        raise SyncError("GITHUB_UNAVAILABLE")

    def json(self, path):
        # Only the website's SHA-to-SHA comparison may contain consecutive dots.
        # Do not relax this to a substring check: traversal must remain rejected.
        comparison = re.fullmatch(
            rf"/repos/{re.escape(WEBSITE)}/compare/[a-f0-9]{{40}}\.\.\.[a-f0-9]{{40}}", path)
        require(path.startswith("/repos/") and
                not any(c in path for c in "%\\#") and
                not any(ord(c) < 33 or ord(c) == 127 for c in path) and
                (".." not in path or comparison is not None), "BAD_API_PATH")
        cachefile = self.cache / (hashlib.sha256(path.encode()).hexdigest() + ".json")
        cached = json.loads(cachefile.read_text()) if cachefile.exists() else None
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if cached and cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        try:
            with self.open("https://api.github.com" + path, headers) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
                require(len(raw) <= 16 * 1024 * 1024, "API_RESPONSE_TOO_LARGE")
                data = json.loads(raw)
                atomic_json(cachefile, {"etag": response.headers.get("ETag"), "data": data})
                return data
        except urllib.error.HTTPError as exc:
            require(exc.code == 304 and cached is not None, "INVALID_NOT_MODIFIED")
            return cached["data"]

    def pages(self, path):
        result = []
        for page in range(1, 21):
            data = self.json(path + f"?per_page=100&page={page}")
            require(isinstance(data, list), "INVALID_API_COLLECTION")
            result.extend(data)
            if len(data) < 100:
                return result
        raise SyncError("API_PAGINATION_LIMIT")

    def releases(self, repo):
        return self.pages(f"/repos/{repo}/releases")

    def release(self, repo, release_id):
        result = self.json(f"/repos/{repo}/releases/{release_id}")
        result["assets"] = self.pages(f"/repos/{repo}/releases/{release_id}/assets")
        return result

    def inspect(self, repo, release):
        result = dict(release)
        result["assets"] = self.pages(f"/repos/{repo}/releases/{release['id']}/assets")
        return result

    def download(self, asset, destination):
        """Restart bounded failed transfers; never append or execute payloads."""
        for attempt in range(3):
            started = time.monotonic()
            try:
                with self.open(asset["url"]) as response, destination.open("wb") as output:
                    length = response.headers.get("Content-Length")
                    require(length is None or length == str(asset["size"]), "DOWNLOAD_SIZE_HEADER")
                    size, sha = 0, hashlib.sha256()
                    while True:
                        require(time.monotonic() - started < 600, "DOWNLOAD_DEADLINE")
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        require(size <= asset["size"], "DOWNLOAD_TOO_LARGE")
                        output.write(chunk)
                        sha.update(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                require(size == asset["size"], "DOWNLOAD_SIZE_MISMATCH")
                require(sha.hexdigest() == asset["sha256"], "DOWNLOAD_HASH_MISMATCH")
                return
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise SyncError("DOWNLOAD_INTERRUPTED") from None
                time.sleep(2 ** attempt)


def select_releases(releases):
    result = {}
    for release in releases:
        require(type(release.get("draft")) is bool and type(release.get("prerelease")) is bool,
                "INVALID_RELEASE_FLAGS")
        if release["draft"] or release["prerelease"]:
            continue
        tag = release.get("tag_name", "")
        require(isinstance(tag, str) and tag.startswith("v"), "UNSUPPORTED_STABLE_TAG")
        version = tag[1:]
        key(version)
        require(version not in result, "DUPLICATE_RELEASE_VERSION")
        require(type(release.get("id")) is int and release["id"] > 0 and
                release.get("published_at"), "INVALID_RELEASE_IDENTITY")
        result[version] = release
    return dict(sorted(result.items(), key=lambda item: key(item[0]), reverse=True))


def release_record(product, release):
    repo = PRODUCTS[product]
    require(type(release.get("draft")) is bool and type(release.get("prerelease")) is bool and
            type(release.get("id")) is int and release["id"] > 0,
            "INVALID_RELEASE_IDENTITY")
    require(not release.get("draft") and not release.get("prerelease"), "NOT_STABLE")
    published = release.get("published_at", "")
    require(isinstance(published, str) and published.endswith("Z"), "INVALID_PUBLICATION_TIME")
    try:
        datetime.fromisoformat(published)
    except ValueError:
        raise SyncError("INVALID_PUBLICATION_TIME") from None
    version = release["tag_name"][1:]
    key(version)
    prefix = f"{product}-{version}-"
    files, excluded, observed = {}, [], []
    assets = release.get("assets")
    require(isinstance(assets, list) and len(assets) < 100, "ASSET_LIST_INCOMPLETE")
    names, ids = set(), set()
    for asset in assets:
        name = asset.get("name", "")
        require(isinstance(name, str) and NAME.fullmatch(name) and name not in names,
                "INVALID_OR_DUPLICATE_ASSET_NAME")
        asset_id = asset.get("id")
        require(type(asset_id) is int and asset_id > 0 and asset_id not in ids,
                "INVALID_ASSET_ID")
        ids.add(asset_id)
        names.add(name)
        observed.append({field: asset.get(field) for field in
                         ("id", "name", "size", "digest", "updated_at", "state", "browser_download_url")})
        suffix = name[len(prefix):] if name.startswith(prefix) else ""
        installer = bool(INSTALLER.fullmatch(suffix))
        provenance = suffix.endswith(".provenance.json") and bool(
            INSTALLER.fullmatch(suffix.removesuffix(".provenance.json")))
        checksum = name in ("SHA256SUMS", "SHA256SUMS.txt")
        source = name == prefix + "source.zip"
        if not (installer or provenance or checksum):
            require(not ARCHIVE.search(name) or source, "UNRECOGNIZED_INSTALLER_REQUIRES_REVIEW")
            excluded.append(name)
            continue
        sha = asset.get("digest", "")
        require(isinstance(sha, str) and sha.startswith("sha256:") and SHA.fullmatch(sha[7:]),
                "MISSING_TRUSTED_SHA256")
        size = asset.get("size")
        require(type(size) is int and 0 < size <= 4 * 1024 ** 3 and
                asset.get("state") == "uploaded", "INVALID_ASSET_SIZE_OR_STATE")
        url = f"https://github.com/{repo}/releases/download/v{version}/{name}"
        require(asset.get("browser_download_url") == url, "ASSET_REPO_VERSION_MISMATCH")
        files[name] = {"id": asset_id, "size": size, "sha256": sha[7:], "url": url,
                       "installer": installer}
    require(any(a["installer"] for a in files.values()), "NO_SUPPORTED_INSTALLERS")
    identity = {"id": release["id"], "tag": release["tag_name"],
                "published_at": release["published_at"],
                "assets": sorted(observed, key=lambda a: a["name"])}
    return {"product": product, "repo": repo, "version": version,
            "identity": identity, "files": files, "excluded": sorted(excluded)}


def inventory(directory, record):
    expected = set(record["files"]) | {"_release.json", "SHA256SUMS.mirror.txt"}
    require(directory.is_dir() and not directory.is_symlink(), "MIRROR_DIRECTORY_MISSING")
    require({p.name for p in directory.iterdir()} == expected, "UNMANAGED_FILES_PRESENT")
    for name, asset in record["files"].items():
        path = confined(directory, name)
        require(path.stat().st_size == asset["size"] and digest(path) == asset["sha256"],
                "LOCAL_ASSET_INTEGRITY")
    require(json.loads((directory / "_release.json").read_text()) == record, "LOCAL_RECORD_CHANGED")
    require((directory / "SHA256SUMS.mirror.txt").read_text() == checksum_text(record),
            "LOCAL_CHECKSUM_CHANGED")


def checksum_text(record):
    return "".join(f"{asset['sha256']}  {name}\n" for name, asset in sorted(record["files"].items()))


def check_release_checksums(directory, record):
    for name in ("SHA256SUMS", "SHA256SUMS.txt"):
        if name not in record["files"]:
            continue
        checksums = {}
        for line in (directory / name).read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            match = re.fullmatch(r"([a-fA-F0-9]{64}) [ *]([A-Za-z0-9.\-]+)", line)
            require(match is not None and match[2] not in checksums, "INVALID_CHECKSUM_METADATA")
            checksums[match[2]] = match[1].lower()
        for filename, asset in record["files"].items():
            if asset["installer"]:
                require(checksums.get(filename) == asset["sha256"], "CHECKSUM_METADATA_CONFLICT")


class Engine:
    def __init__(self, config, github=None):
        self.config = config
        self.root = Path(config["root"])
        require(self.root.is_absolute() and not self.root.is_symlink(), "UNSAFE_ROOT")
        self.root.mkdir(parents=True, exist_ok=True)
        # Parent directories must be provisioned by the administrator, never world-writable.
        for relative in ("private", "private/staging", "private/cache", "private/plans",
                         "private/quarantine", "public", "public/mirror", "public/sites", "public/site-sets"):
            path = confined(self.root, relative)
            path.mkdir(exist_ok=True, parents=True)
            path.chmod(0o700 if relative.startswith("private") else 0o755)
        self.private = self.root / "private"
        self.public = self.root / "public"
        self.state_path = confined(self.root, "private/state.json")
        self.api = github or GitHub(self.private / "cache")
        self.state = self.read_state()
        from site_builder import recover_website
        recover_website(self)

    def read_state(self):
        if not self.state_path.exists():
            return {"schema": 1, "records": {}, "observations": {}, "website": None}
        value = json.loads(self.state_path.read_text())
        require(value.get("schema") == 1, "UNKNOWN_STATE_SCHEMA")
        return value

    def save(self):
        atomic_json(self.state_path, self.state)

    def space(self, required):
        require(shutil.disk_usage(self.root).free >= required + self.config.get("reserve_bytes", 2 * 1024 ** 3),
                "INSUFFICIENT_DISK_SPACE")

    def activation(self):
        receipt = Path(self.config["activation_receipt"])
        require(receipt.is_file() and not receipt.is_symlink(), "MIGRATION_RECEIPT_REQUIRED")
        data = json.loads(receipt.read_text())
        require(data.get("base_commit") == "8adb58a7a3dd1f169ed4977a62404e30a84ed01e" and
                SHA.fullmatch(data.get("server_patch_sha256", "")) and
                SHA.fullmatch(data.get("legacy_backup_sha256", "")) and
                data.get("patch_reconciled") is True and data.get("nginx_checked") is True,
                "MIGRATION_NOT_VERIFIED")

    def manifest(self):
        products = {p: {"repo": repo, "versions": {}} for p, repo in PRODUCTS.items()}
        for record in self.state["records"].values():
            if record["status"] != "ready":
                continue
            product, version = record["product"], record["version"]
            files = {name: {"size": a["size"], "sha256": a["sha256"],
                            "path": f"/mirror/v1/{product.lower()}/{version}/{name}"}
                     for name, a in record["release"]["files"].items() if a["installer"]}
            products[product]["versions"][version] = {"files": files}
        atomic_json(confined(self.root, "public/mirror/index.json"),
                    {"schema": 1, "products": products}, 0o644)

    def sync_release(self, product, release):
        record = release_record(product, release)
        version = record["version"]
        record_id = product + "/" + version
        observed = self.state["observations"].get(record_id)
        require(observed is None or observed == record["identity"], "UPSTREAM_ASSET_CHANGED")
        self.state["observations"][record_id] = record["identity"]
        self.save()  # TOFU journal before downloads; a later replacement cannot be silently accepted.
        prior = self.state["records"].get(record_id)
        destination = confined(self.root, f"public/mirror/{product.lower()}/{version}")
        if prior:
            require(prior["release"] == record, "UPSTREAM_ASSET_CHANGED")
            if prior["status"] == "quarantined":
                return "quarantined"
            if destination.exists():
                inventory(destination, record)
                prior["status"] = "ready"  # Recover a rename committed before the state write.
                self.save()
                return "unchanged"
        require(not destination.exists(), "UNMANAGED_DESTINATION_EXISTS")
        self.space(sum(a["size"] for a in record["files"].values()))
        stage = confined(self.root, "private/staging/" + uuid.uuid4().hex)
        stage.mkdir(mode=0o700)
        for name, asset in record["files"].items():
            self.api.download(asset, stage / name)
            require((stage / name).stat().st_size == asset["size"] and
                    digest(stage / name) == asset["sha256"], "DOWNLOAD_INTEGRITY")
        check_release_checksums(stage, record)
        # Re-read trusted metadata after the transfer, before making anything public.
        fresh = release_record(product, self.api.release(PRODUCTS[product], release["id"]))
        require(fresh == record, "UPSTREAM_CHANGED_DURING_DOWNLOAD")
        atomic_json(stage / "_release.json", record, 0o644)
        (stage / "SHA256SUMS.mirror.txt").write_text(checksum_text(record), encoding="utf-8")
        for path in stage.iterdir():
            path.chmod(0o644)
        stage.chmod(0o755)
        inventory(stage, record)
        sync_tree(stage)
        self.state["records"][record_id] = {"product": product, "version": version,
                                            "status": "pending", "release": record}
        self.save()
        destination.parent.mkdir(exist_ok=True, mode=0o755)
        require(not destination.exists(), "DESTINATION_RACE")
        os.replace(stage, destination)
        sync_dir(destination.parent)
        self.state["records"][record_id]["status"] = "ready"
        self.save()
        return "published"

    def sync_product(self, product):
        releases = select_releases(self.api.releases(PRODUCTS[product]))
        require(releases, "NO_STABLE_RELEASES")
        # Select the newest FIVE SUCCESSES, not merely five upstream tags.
        # Invalid/missing-digest releases do not consume a transfer or retention
        # slot. Retained older versions are still inspected for upstream changes.
        managed = {
            r["version"] for r in self.state["records"].values()
            if r["product"] == product and r["status"] in ("ready", "pending", "held")}
        errors, transferred, successes = [], 0, 0
        unresolved = self.state.setdefault('release_failures',{})
        budget = self.config.get('backfill_per_run',1)
        require(type(budget) is int and 1 <= budget <= 5, 'INVALID_BACKFILL_BUDGET')
        for version in sorted(set(releases)|managed, key=key, reverse=True):
            try:
                require(version in releases, "MANAGED_RELEASE_REMOVED_OR_NOT_STABLE")
                release = releases[version]
                record_id = product + "/" + version
                prior = self.state['records'].get(record_id)
                if prior and prior['status'] in ('quarantined','quarantining','restoring'):
                    continue  # Operator quarantine is not automatically undone.
                deferred = False
                if version not in managed:
                    if successes >= 5:
                        continue
                    if transferred >= budget:
                        if record_id not in unresolved:
                            continue
                        deferred = True  # Do not hide a previously reported anomaly.
                elif prior['status'] == 'pending' and transferred >= budget:
                    destination = confined(self.root,f'public/mirror/{product.lower()}/{version}')
                    if not destination.exists():
                        continue
                # Enumerate the asset endpoint; do not assume an embedded array
                # in a collection response is complete.
                full = self.api.inspect(PRODUCTS[product], release)
                require(full.get("id") == release["id"] and full.get("tag_name") == "v" + version,
                        "RELEASE_CHANGED_DURING_INSPECTION")
                release = full
                if deferred:
                    record = release_record(product,release)
                    observed = self.state['observations'].get(record_id)
                    require(observed is None or observed==record['identity'],'UPSTREAM_ASSET_CHANGED')
                    unresolved.pop(record_id,None)
                    self.save()
                    log('release_deferred',product=product,version=version,reason='success_budget')
                    continue
                result = self.sync_release(product, release)
                unresolved.pop(record_id,None)
                self.save()
                if result == 'published':
                    transferred += 1
                if self.state['records'][record_id]['status'] == 'ready':
                    successes += 1
                log("release", product=product, version=version, result=result)
            except (SyncError, OSError, ValueError, KeyError, TypeError) as exc:
                code = str(exc) if isinstance(exc, SyncError) else type(exc).__name__
                retained = self.state["records"].get(product + "/" + version)
                if retained and retained["status"] in ("ready", "held"):
                    retained["status"] = "held"
                    self.save()
                errors.append({"version": version, "code": code})
                unresolved[product+'/'+version]={'code':code,'last_checked':int(time.time())}
                self.save()
                log("release_failed", product=product, version=version, code=code)
                if code in ('GITHUB_RATE_LIMIT_OR_FORBIDDEN','GITHUB_UNAVAILABLE'):
                    break
        require(not errors, "PRODUCT_SYNC_FAILED")

    def pins(self):
        """Both pages in the active pointer set are protected, including after rollback."""
        from site_builder import page_pins
        return page_pins(self)

    def plan(self):
        pins = self.pins()
        candidates, protected = [], []
        for product in PRODUCTS:
            records = sorted((r for r in self.state["records"].values()
                              if r["product"] == product and r["status"] == "ready"),
                             key=lambda r: key(r["version"]), reverse=True)
            for record in records[5:]:
                version = record["version"]
                if version in pins.get(product, set()):
                    protected.append(product + "/" + version)
                    continue
                path = confined(self.root, f"public/mirror/{product.lower()}/{version}")
                inventory(path, record["release"])
                candidates.append({"id": product + "/" + version,
                                   "fingerprint": hashlib.sha256(encoded(record["release"])).hexdigest()})
        plan = {"schema": 1, "id": uuid.uuid4().hex, "created": int(time.time()),
                "action": "reversible-quarantine-only", "candidates": candidates,
                "protected": sorted(protected), "state_sha256": hashlib.sha256(encoded(self.state)).hexdigest()}
        atomic_json(self.private / "plans" / (plan["id"] + ".json"), plan)
        log("cleanup_plan", plan=plan["id"], candidates=len(candidates), protected=protected)
        return plan

    def quarantine(self, plan_id):
        require(re.fullmatch(r"[a-f0-9]{32}", plan_id), "INVALID_PLAN_ID")
        plan = json.loads((self.private / "plans" / (plan_id + ".json")).read_text())
        require(plan.get("id") == plan_id and plan.get("action") == "reversible-quarantine-only" and
                0 <= time.time() - plan["created"] < 86400, "INVALID_OR_EXPIRED_PLAN")
        require(plan["state_sha256"] == hashlib.sha256(encoded(self.state)).hexdigest(), "STALE_PLAN")
        # Validate the entire plan again before the first move.
        current = self.plan()
        require(plan["candidates"] == current["candidates"], "PAGE_PINS_OR_INVENTORY_CHANGED")
        for candidate in plan["candidates"]:
            record = self.state["records"][candidate["id"]]
            product, version = record["product"], record["version"]
            source = confined(self.root, f"public/mirror/{product.lower()}/{version}")
            target = confined(self.root, f"private/quarantine/{product.lower()}-{version}-{plan_id}")
            require(not target.exists(), "QUARANTINE_EXISTS")
            # Journal before rename; index withdraw happens first. Bytes remain recoverable.
            record["status"], record["quarantine"] = "quarantining", target.name
            self.save()
            self.manifest()
            os.replace(source, target)
            sync_dir(target.parent)
            record["status"] = "quarantined"
            self.save()
            log("quarantined", product=product, version=version)

    def restore(self, product, version):
        require(product in PRODUCTS, "UNKNOWN_PRODUCT")
        key(version)
        record = self.state["records"][product + "/" + version]
        require(record["status"] in ("quarantined", "quarantining", "restoring"), "NOT_QUARANTINED")
        source = confined(self.root, "private/quarantine/" + record["quarantine"])
        target = confined(self.root, f"public/mirror/{product.lower()}/{version}")
        if source.exists():
            inventory(source, record["release"])
            require(not target.exists(), "RESTORE_DESTINATION_EXISTS")
            record["status"] = "restoring"
            self.save()
            os.replace(source, target)
            sync_dir(target.parent)
        else:
            inventory(target, record["release"])  # interrupted move: already at destination
        record["status"] = "ready"
        self.save()
        self.manifest()
        log("restored", product=product, version=version)

    def run(self, build=None):
        self.activation()
        old_status = self.private / "status.json"
        old = json.loads(old_status.read_text()) if old_status.exists() else {}
        status = {"schema": 1, "checked_at": int(time.time()), "components": {}}
        for product in PRODUCTS:
            try:
                self.sync_product(product)
                status["components"][product] = {"ok": True}
            except (SyncError, OSError, ValueError, KeyError, TypeError) as exc:
                status["components"][product] = {"ok": False, "code":
                    str(exc) if isinstance(exc, SyncError) else type(exc).__name__}
        # A failure of one product must not suppress a success of the other or the website.
        self.manifest()
        try:
            from site_builder import sync_website
            (build or sync_website)(self)
            status["components"]["website"] = {"ok": True}
        except (SyncError, OSError, ValueError, KeyError, TypeError) as exc:
            status["components"]["website"] = {"ok": False, "code":
                str(exc) if isinstance(exc, SyncError) else type(exc).__name__}
        # No cleanup is performed by the scheduled task. Every plan remains reviewable.
        try:
            status["cleanup_plan"] = self.plan()["id"]
        except (SyncError, OSError, ValueError, KeyError, TypeError) as exc:
            status["components"]["cleanup"] = {"ok": False, "code":
                str(exc) if isinstance(exc, SyncError) else type(exc).__name__}
        for component, value in status["components"].items():
            value["last_success"] = status["checked_at"] if value["ok"] else \
                old.get("components", {}).get(component, {}).get("last_success")
        atomic_json(self.private / "status.json", status)
        log("run_complete", **status)
        return all(item["ok"] for item in status["components"].values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("command", choices=("run", "plan", "quarantine", "restore", "rollback", "resume-site", "status"))
    parser.add_argument("arguments", nargs="*")
    args = parser.parse_args()
    try:
        config = json.loads(Path(args.config).read_text())
        root = Path(config["root"])
        require(root.is_absolute() and not root.is_symlink(), "UNSAFE_ROOT")
        with locked(confined(root, "private/run.lock")):
            engine = Engine(config)
            if args.command == "run":
                return 0 if engine.run() else 1
            if args.command == "plan":
                log("plan", plan=engine.plan())
            elif args.command == "quarantine":
                require(len(args.arguments) == 1, "EXPECTED_PLAN_ID")
                engine.quarantine(args.arguments[0])
            elif args.command == "restore":
                require(len(args.arguments) == 2, "EXPECTED_PRODUCT_VERSION")
                engine.restore(*args.arguments)
            elif args.command == "rollback":
                from site_builder import rollback
                rollback(engine)
            elif args.command == "resume-site":
                from site_builder import resume_website
                resume_website(engine)
            elif args.command == "status":
                log("status", status=json.loads((engine.private / "status.json").read_text()))
        return 0
    except Exception as exc:
        log("fatal", code=str(exc) if isinstance(exc, SyncError) else type(exc).__name__)
        return 1


if __name__ == "__main__":
    # Run through the same module identity imported by the build/storage helpers.
    # The second module load defines symbols only; the command executes once.
    from amber_sync import main as canonical_main
    sys.exit(canonical_main())
