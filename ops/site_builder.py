"""Isolated build, static validation and atomic current/previous pointer sets."""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import urllib.parse
import uuid

from amber_sync import (PRODUCTS, WEBSITE, SyncError, atomic_json, confined,
                        digest, encoded, key, log, require, sync_dir, sync_tree)
from storage import PublicationSpace

NODE = "24.22.1"
PNPM = "11.25.0"
COMMIT = re.compile(r"[a-f0-9]{40}\Z")


def command(argv, cwd, env=None, timeout=300):
    try:
        result = subprocess.run(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SyncError("BUILD_COMMAND_TIMEOUT_OR_UNAVAILABLE") from exc
    # Do not dump dependency script output: it can contain personal paths or credentials.
    if result.returncode:
        (cwd / "command-failure.log").write_bytes(result.stdout[-1024 * 1024:])
        raise SyncError("BUILD_COMMAND_FAILED")
    return result.stdout


def extract_source(data, destination):
    """Git archives only: no symlinks, hardlinks, devices, traversal or metadata paths."""
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        total = 0
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and ".." not in path.parts and "\\" not in member.name,
                    "SOURCE_PATH_ESCAPE")
            require(all(p not in (".git", "node_modules", "dist") for p in path.parts),
                    "UNEXPECTED_SOURCE_CONTENT")
            require(member.isdir() or member.isfile(), "SOURCE_LINK_OR_SPECIAL_FILE")
            total += member.size
            require(total < 512 * 1024 ** 2, "SOURCE_TOO_LARGE")
            target = confined(destination, str(path))
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)


def source_pins(source):
    catalog = json.loads((source / "src/download-catalog.json").read_text())
    require(set(catalog) == set(PRODUCTS), "INVALID_DOWNLOAD_CATALOG")
    pins = {product: {entry["version"]} for product, entry in catalog.items()}
    for product, entry in catalog.items():
        require(entry["repo"] == PRODUCTS[product], "CATALOG_PRODUCT_MISMATCH")
        key(entry["version"])
    # Protect literal historical release links elsewhere in the site as well.
    # Vite-managed UI images/fonts now live under src; they are not UTF-8 source.
    binary_assets = {".woff", ".woff2", ".ttf", ".otf", ".png", ".jpg", ".jpeg",
                     ".webp", ".avif", ".gif", ".ico"}
    for path in (source / "src").rglob("*"):
        if path.is_file() and path.suffix.lower() not in binary_assets:
            for version in re.findall(r"(?:/v|\bv)(\d+\.\d+\.\d+)\b", path.read_text(encoding="utf-8")):
                for product in PRODUCTS:
                    pins[product].add(version)
    return {p: sorted(versions, key=key) for p, versions in pins.items()}


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for attribute in ("src", "href", "poster"):
            if attribute in attrs:
                self.urls.append(attrs[attribute])
        if attrs.get("srcset"):
            self.urls.extend(item.strip().split()[0] for item in attrs["srcset"].split(","))


def validate_static(directory):
    require((directory / "index.html").is_file(), "STATIC_INDEX_MISSING")
    count = 0
    for path in directory.rglob("*"):
        require(not path.is_symlink() and (path.is_file() or path.is_dir()), "STATIC_SPECIAL_FILE")
        if not path.is_file():
            continue
        count += 1
        require(count <= 10000, "TOO_MANY_STATIC_FILES")
        require(path.suffix.lower() not in (".php", ".py", ".sh", ".pem", ".key"),
                "NON_STATIC_OR_SECRET_FILE")
        require(path.relative_to(directory).parts[0] not in ("downloads", "mirror", "private", ".git"),
                "RESERVED_STATIC_PATH")
        urls = []
        if path.suffix == ".html":
            parser = References()
            parser.feed(path.read_text(encoding="utf-8"))
            urls.extend(parser.urls)
        if path.suffix in (".css", ".js"):
            text = path.read_text(encoding="utf-8")
            urls.extend(re.findall(r"url\(\s*['\"]?([^)'\"\s]+)", text))
            # Vite emitted imports and root-relative public asset references.
            urls.extend(url for url in re.findall(r"['\"]((?:\./|/)?(?:assets|themes)/[^'\"<>]+)['\"]", text)
                        if PurePosixPath(urllib.parse.urlsplit(url).path).suffix)
            if path.suffix == ".js":
                urls.extend(re.findall(r"(?:from\s*|import\s*)['\"](\./[^'\"]+)['\"]", text))
        for url in urls:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme or parsed.netloc or not parsed.path or url.startswith("#"):
                continue
            relative = urllib.parse.unquote(parsed.path)
            target = directory / relative.lstrip("/") if relative.startswith("/") else path.parent / relative
            require(target.resolve().is_relative_to(directory.resolve()) and target.is_file() and
                    not target.is_symlink(), "STATIC_REFERENCE_MISSING")
    return count


def copy_static(source, destination, file_mode=0o640, directory_mode=0o750, space=None):
    """Copy bytes only, with explicit permissions; never carry setgid or xattrs.

    Builder directories inherit the sync group for read access. The builder
    deliberately is not a member of that group, so copying setgid metadata
    with shutil.copytree/copystat can fail or propagate unwanted permissions.
    """
    validate_static(source)
    require(not destination.exists(), 'STATIC_COPY_DESTINATION_EXISTS')
    if space:
        files=[p for p in source.rglob('*') if p.is_file()]
        dirs=[p for p in source.rglob('*') if p.is_dir()]
        space.check(sum(space.allocated(p.stat().st_size) for p in files)+(len(dirs)+1)*space.block+65536)
        space.directory(destination)
    else:
        destination.mkdir(mode=directory_mode)
    for path in sorted(source.rglob('*')):
        target = destination / path.relative_to(source)
        if path.is_dir():
            if space: space.directory(target)
            else: target.mkdir(parents=True, exist_ok=True, mode=directory_mode)
        else:
            target.parent.mkdir(parents=True, exist_ok=True, mode=directory_mode)
            if space: space.copy(path,target,path.stat().st_size)
            else: shutil.copyfile(path, target)
            target.chmod(file_mode)
    for directory in sorted((p for p in destination.rglob('*') if p.is_dir()), reverse=True):
        directory.chmod(directory_mode)
    destination.chmod(directory_mode)


def deployment(engine, name):
    require(COMMIT.fullmatch(name), "INVALID_DEPLOYMENT_NAME")
    path = confined(engine.root, "public/sites/" + name)
    data = json.loads((path / "_amber-deployment.json").read_text())
    require(data.get("commit") == name and set(data.get("pins", {})) == set(PRODUCTS),
            "INVALID_DEPLOYMENT_METADATA")
    for versions in data["pins"].values():
        for version in versions:
            key(version)
    return path, data


def active_pair(engine):
    active = engine.public / "active"
    if not active.is_symlink():
        require(not active.exists(), "UNMANAGED_ACTIVE_DIRECTORY")
        return None, None
    link = os.readlink(active)
    require(re.fullmatch(r"site-sets/[a-f0-9]{32}", link), "UNSAFE_ACTIVE_LINK")
    pointer_set = confined(engine.root, "public/" + link)
    result = []
    for name in ("current", "previous"):
        path = pointer_set / name
        if not path.is_symlink():
            require(not path.exists() and name == "previous", "INVALID_SITE_POINTER")
            result.append(None)
            continue
        target = os.readlink(path)
        require(re.fullmatch(r"../../sites/[a-f0-9]{40}", target), "UNSAFE_SITE_POINTER")
        commit = target.rsplit("/", 1)[1]
        deployment(engine, commit)
        result.append(commit)
    return tuple(result)


def page_pins(engine):
    pins = {p: set() for p in PRODUCTS}
    for name in active_pair(engine):
        if name:
            _, data = deployment(engine, name)
            for product, versions in data["pins"].items():
                pins[product].update(versions)
    return pins


def switch(engine, current, previous):
    require(os.name == "posix", "POSIX_ATOMIC_SYMLINKS_REQUIRED")
    for commit in (current, previous):
        if commit:
            path, _ = deployment(engine, commit)
            validate_static(path)
    # A generation contains BOTH pointers. One atomic rename commits the pair.
    generation = engine.public / "site-sets" / uuid.uuid4().hex
    generation.mkdir(mode=0o755)
    os.symlink("../../sites/" + current, generation / "current")
    if previous:
        os.symlink("../../sites/" + previous, generation / "previous")
    sync_dir(generation)
    # Persist the generation's directory entry before active can reference it.
    sync_dir(generation.parent)
    link = engine.public / ("active-" + uuid.uuid4().hex)
    os.symlink("site-sets/" + generation.name, link)
    os.replace(link, engine.public / "active")
    sync_dir(engine.public)


def rollback(engine):
    recover_website(engine)
    website = engine.state.get('website') or {}
    if website.get('paused') and website.get('rollback', {}).get('phase') == 'complete':
        log('website_rollback_already_complete', commit=website['commit'])
        return
    current, previous = active_pair(engine)
    require(current and previous and current != previous, "NO_ROLLBACK_AVAILABLE")
    # Write-ahead decision: pause is durable BEFORE any public pointer changes.
    # Recovery accepts either side of the atomic rename and finishes idempotently.
    transaction = {'id':uuid.uuid4().hex, 'phase':'pending',
                   'from':[current,previous], 'to':[previous,current]}
    engine.state['website'] = {'commit':current,'paused':True,'rollback':transaction}
    engine.save()
    transaction_checkpoint('rollback_intent_saved')
    recover_website(engine)


def transaction_checkpoint(name):
    """No-op in production; process-exit fault injection is patched in tests."""


def recover_website(engine):
    website = engine.state.get('website') or {}
    transaction = website.get('rollback')
    if not transaction or transaction.get('phase') == 'complete':
        return
    require(transaction.get('phase') == 'pending' and website.get('paused') is True,
            'INVALID_ROLLBACK_TRANSACTION')
    before, target = transaction.get('from'), transaction.get('to')
    require(isinstance(before,list) and len(before)==2 and
            isinstance(target,list) and len(target)==2 and target==list(reversed(before)) and
            all(isinstance(c,str) and COMMIT.fullmatch(c) for c in before) and before[0]!=before[1],
            'INVALID_ROLLBACK_TRANSACTION')
    pair = active_pair(engine)
    require(pair in (tuple(before),tuple(target)), 'ROLLBACK_POINTER_CONFLICT')
    if pair == tuple(before):
        switch(engine,*target)
    transaction_checkpoint('rollback_pointer_switched')
    engine.state['website'] = {'commit':target[0],'paused':True,
        'rollback':{**transaction,'phase':'complete'}}
    engine.save()
    transaction_checkpoint('rollback_complete_saved')
    log('website_rollback',commit=target[0],paused=True,transaction=transaction['id'])


def resume_website(engine):
    recover_website(engine)
    require(engine.state.get('website'), 'NO_WEBSITE_STATE')
    current, _ = active_pair(engine)
    require(current, 'NO_ACTIVE_WEBSITE')
    # Clear the completed transaction and unpause in ONE durable state write.
    engine.state['website'] = {'commit':current,'paused':False}
    engine.save()
    log('website_resumed',commit=current)


def publication_plan(engine, static, current, metadata):
    """Exact union: new files plus distinct historical assets, never duplicates."""
    files = {p.relative_to(static).as_posix():(p,p.stat().st_size)
             for p in static.rglob('*') if p.is_file()}
    if current:
        old_assets = engine.public / 'sites' / current / 'assets'
        if old_assets.exists():
            require(not old_assets.is_symlink(), 'OLD_ASSET_SYMLINK')
            for old in old_assets.rglob('*'):
                require(not old.is_symlink() and (old.is_dir() or old.is_file()), 'OLD_ASSET_SYMLINK')
                if old.is_file():
                    name = 'assets/' + old.relative_to(old_assets).as_posix()
                    if name in files:
                        require(digest(files[name][0])==digest(old), 'STATIC_ASSET_NAME_COLLISION')
                    else:
                        files[name] = (old,old.stat().st_size)
    directories = {'.'}
    for name in files:
        directories.update(p.as_posix() for p in Path(name).parents)
    guard = PublicationSpace(engine)
    budget = sum(guard.allocated(size) for _,size in files.values())
    budget += guard.allocated(len(metadata)) + len(directories)*guard.block + 65536
    return files,directories,guard,budget


def publish_site(engine, source, static, commit):
    require(COMMIT.fullmatch(commit), "INVALID_MAIN_COMMIT")
    validate_static(static)
    require(not (static / "_amber-deployment.json").exists(), "RESERVED_DEPLOYMENT_METADATA")
    current, _ = active_pair(engine)
    destination = confined(engine.root, "public/sites/" + commit)
    require(not destination.exists(), "DEPLOYMENT_ALREADY_EXISTS")
    metadata = {'schema':1,'commit':commit,'pins':source_pins(source)}
    metadata_bytes = encoded(metadata) + b'\n'
    files,directories,guard,budget = publication_plan(engine,static,current,metadata_bytes)
    guard.check(budget)
    candidate = engine.private / "staging" / uuid.uuid4().hex
    guard.directory(candidate)
    for directory in sorted(directories,key=lambda p:(len(Path(p).parts),p)):
        if directory != '.':
            guard.directory(candidate / directory)
    for name,(path,size) in sorted(files.items()):
        guard.copy(path,candidate / name,size)
    guard.write(metadata_bytes,candidate / '_amber-deployment.json')
    validate_static(candidate)
    for path in candidate.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    candidate.chmod(0o755)
    sync_tree(candidate)
    guard.check(65536 + len(encoded(engine.state)))
    os.replace(candidate, destination)
    sync_dir(destination.parent)
    switch(engine, commit, current)
    engine.state["website"] = {"commit": commit, "paused": False}
    engine.save()
    log("website_published", commit=commit, previous=current)


def build_tools(work, tools):
    """Validate the exact toolchain and return a CLEAN process environment."""
    require(os.name == "posix" and os.getuid() != 0, "UNPRIVILEGED_LINUX_BUILDER_REQUIRED")
    marker = Path('/.amber-build-jail')
    require(marker.is_file() and marker.stat().st_uid == 0 and
            marker.read_text().strip() == 'AMBER build jail v1', "SYSTEMD_BUILD_JAIL_REQUIRED")
    require(tools == Path('/tools') and work.is_relative_to(Path('/build')) and
            (tools / 'node/bin/node').is_file() and (tools / 'pnpm/bin/pnpm.cjs').is_file(),
            "PINNED_TOOLS_MISSING")
    env = {"PATH": "/tools/node/bin:/usr/bin:/bin", "HOME": str(work / '.home'),
           "CI": "true", "LANG": "C.UTF-8", 'pnpm_config_ignore_pnpmfile':'true'}
    node = '/tools/node/bin/node'
    require(command([node, "--version"], work, env).decode().strip() == "v" + NODE,
            "NODE_VERSION_MISMATCH")
    # Even `pnpm --version` can load project hooks unless explicitly disabled.
    pnpm = [node, "/tools/pnpm/bin/pnpm.cjs"]
    require(command(pnpm + ['--ignore-pnpmfile',"--version"], work, env).decode().strip() == PNPM,
            "PNPM_VERSION_MISMATCH")
    package = json.loads((work / "package.json").read_text())
    require(package.get("packageManager") == "pnpm@" + PNPM and
            (work / ".node-version").read_text().strip() == NODE,
            "REPOSITORY_TOOL_PIN_MISMATCH")
    require((work / "pnpm-lock.yaml").is_file(), "LOCKFILE_MISSING")
    return pnpm,env


def install_dependencies(work,tools):
    from network_guard import network_guard
    from registry_proxy import install_bridge
    policy=network_guard(work,'install')
    pnpm,env=build_tools(work,tools)
    lock_hash=digest(work/'pnpm-lock.yaml')
    with install_bridge() as proxy:
        env.update(HTTPS_PROXY=proxy,HTTP_PROXY=proxy,https_proxy=proxy,http_proxy=proxy,
                   NO_PROXY='',no_proxy='',NODE_TLS_REJECT_UNAUTHORIZED='1')
        command(pnpm+['install','--frozen-lockfile','--ignore-scripts','--ignore-pnpmfile',
                     '--config.strict-ssl=true','--registry=https://registry.npmjs.org/',
                     '--config.https-proxy='+proxy,'--config.proxy='+proxy,
                     '--network-concurrency=8','--store-dir',str(work/'.store')],
                work,env,timeout=600)
    require(digest(work/'pnpm-lock.yaml')==lock_hash,'INSTALL_CHANGED_LOCKFILE')
    policy['registry_proxy']='registry.npmjs.org:443'
    return policy


def isolated_build(work, tools):
    """Offline unit only: no IP socket families and no proxy socket mount."""
    from network_guard import network_guard
    policy=network_guard(work,'offline')
    pnpm,env=build_tools(work,tools)
    lock_hash=digest(work/'pnpm-lock.yaml')
    # pnpm 11 `run` may auto-install. Execute the repository's exact scripts
    # directly here; dependency installation belongs ONLY to the previous unit.
    scripts=json.loads((work/'package.json').read_text())['scripts']
    env['PATH']=str(work/'node_modules/.bin')+':'+env['PATH']
    for task,timeout in (('build',300),('test:sites',120),('test:mirror',120)):
        script=scripts.get(task)
        require(isinstance(script,str) and script and '\0' not in script,'REQUIRED_BUILD_SCRIPT_MISSING')
        command(['/bin/sh','-c',script],work,{**env,'npm_lifecycle_event':task},timeout=timeout)
    require(digest(work / "pnpm-lock.yaml") == lock_hash, "BUILD_CHANGED_LOCKFILE")
    return policy


def sync_website(engine):
    recover_website(engine)
    require(not (engine.state.get("website") or {}).get("paused"), "WEBSITE_PAUSED_AFTER_ROLLBACK")
    head = engine.api.json(f"/repos/{WEBSITE}/branches/main")["commit"]["sha"]
    require(COMMIT.fullmatch(head), "INVALID_MAIN_COMMIT")
    current, _ = active_pair(engine)
    if current == head:
        validate_static(engine.public / "sites" / current)
        return
    if current:
        comparison = engine.api.json(f"/repos/{WEBSITE}/compare/{current}...{head}")
        require(comparison.get("status") == "ahead", "WEBSITE_MAIN_REWIND_OR_DIVERGENCE")
    existing = engine.public / "sites" / head
    if existing.exists():
        # Recovery of a candidate whose rename completed before the pointer swap.
        path, _ = deployment(engine, head)
        validate_static(path)
        switch(engine, head, current)
        engine.state["website"] = {"commit": head, "paused": False}
        engine.save()
        return
    engine.space(engine.config.get("build_budget_bytes", 2 * 1024 ** 3))
    work = engine.private / "staging" / uuid.uuid4().hex
    work.mkdir(mode=0o700)
    repository = work / "repository"
    repository.mkdir()
    env = {"PATH": "/usr/bin:/bin", "HOME": str(work / "empty-home"), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_GLOBAL": "/dev/null"}
    command(["git", "init", "--bare"], repository, env)
    command(["git", "-c", "credential.helper=", "-c", "core.hooksPath=/dev/null", "fetch", "--depth=1",
             "https://github.com/" + WEBSITE + ".git", head], repository, env, timeout=180)
    actual = command(["git", "rev-parse", "FETCH_HEAD"], repository, env).decode().strip()
    require(actual == head, "SOURCE_COMMIT_MISMATCH")
    archive = command(["git", "archive", "--format=tar", head], repository, env)
    source = work / "source"
    source.mkdir()
    extract_source(archive, source)
    pins = source_pins(source)
    from build_worker import request_build
    static = request_build(engine, source, head)
    require(source_pins(source) == pins, "BUILD_CHANGED_DOWNLOAD_CATALOG")
    publish_site(engine, source, static, head)
