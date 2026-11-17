import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import amber_sync as sync
import site_builder as site
import build_worker as worker


def fixture(product="AMBER", version="1.7.4"):
    files = {}
    for suffix in ("Setup-x64.exe", "mac-x64.zip", "mac-arm64.zip", "linux-x64.deb",
                   "freebsd-x64-experimental.tar.gz"):
        files[f"{product}-{version}-{suffix}"] = (product + version + suffix).encode()
    files["SHA256SUMS.txt"] = "".join(
        f"{hashlib.sha256(value).hexdigest()}  {name}\n" for name, value in files.items()).encode()
    assets = [{"id": i + 100, "name": name, "size": len(value),
               "digest": "sha256:" + hashlib.sha256(value).hexdigest(), "state": "uploaded",
               "updated_at": "2026-11-17T01:00:00Z", "browser_download_url":
               f"https://github.com/{sync.PRODUCTS[product]}/releases/download/v{version}/{name}"}
              for i, (name, value) in enumerate(files.items())]
    release = {"id": int(version.replace(".", "")) + 1000, "tag_name": "v" + version,
               "published_at": "2026-11-17T01:00:00Z", "draft": False, "prerelease": False, "assets": assets}
    return release, files


class FakeAPI:
    def __init__(self):
        self.data, self.payloads, self.failures = {}, {}, {}
        self.downloads = 0

    def add(self, product="AMBER", version="1.7.4"):
        release, files = fixture(product, version)
        self.data.setdefault(sync.PRODUCTS[product], []).append(release)
        for name, value in files.items():
            self.payloads[release["assets"][[a["name"] for a in release["assets"]].index(name)]["browser_download_url"]] = value
        return release

    def releases(self, repo):
        if repo in self.failures:
            raise sync.SyncError(self.failures[repo])
        return copy.deepcopy(self.data.get(repo, []))

    def release(self, repo, release_id):
        return copy.deepcopy(next(r for r in self.data[repo] if r["id"] == release_id))

    def inspect(self, repo, release):
        return self.release(repo, release['id'])

    def download(self, asset, destination):
        self.downloads += 1
        destination.write_bytes(self.payloads[asset["url"]])


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.api = FakeAPI()
        self.config = {"root": str(self.root), "reserve_bytes": 0, "backfill_per_run": 1,
                       "activation_receipt": str(self.root / "activation.json")}
        sync.atomic_json(self.root / "activation.json", {
            "base_commit": "8adb58a7a3dd1f169ed4977a62404e30a84ed01e", "server_patch_sha256": "a" * 64,
            "legacy_backup_sha256": "b" * 64, "patch_reconciled": True, "nginx_checked": True})
        self.engine = sync.Engine(self.config, self.api)

    def tearDown(self):
        self.temp.cleanup()

    def add_sync(self, product="AMBER", version="1.7.4"):
        release = self.api.add(product, version)
        self.engine.sync_release(product, release)
        return release

    def test_new_version_and_hashes_all_platforms(self):
        self.add_sync()
        self.engine.manifest()
        manifest = json.loads((self.root / "public/mirror/index.json").read_text())
        files = manifest["products"]["AMBER"]["versions"]["1.7.4"]["files"]
        self.assertEqual(len(files), 5)
        for entry in files.values():
            path = self.root / "public/mirror" / entry["path"].removeprefix("/mirror/v1/")
            self.assertEqual(sync.digest(path), entry["sha256"])
        self.assertNotIn("1.7.4", manifest["products"]["AmberE"]["versions"])

    def test_no_update_does_not_redownload(self):
        self.add_sync()
        count = self.api.downloads
        self.engine.sync_product("AMBER")
        self.assertEqual(self.api.downloads, count)

    def test_products_independent_and_site_runs_on_api_failure(self):
        self.api.add("AMBER", "1.7.5")
        self.api.add("AmberE", "1.7.4")
        self.api.failures[sync.PRODUCTS["AMBER"]] = "GITHUB_RATE_LIMIT_OR_FORBIDDEN"
        called = []
        self.assertFalse(self.engine.run(build=lambda engine: called.append(True)))
        self.assertTrue(called)
        self.assertIn("AmberE/1.7.4", self.engine.state["records"])
        status = json.loads((self.root / "private/status.json").read_text())
        self.assertFalse(status["components"]["AMBER"]["ok"])
        self.assertIsNone(status["components"]["AMBER"]["last_success"])
        self.assertTrue(status["components"]["AmberE"]["ok"])

    def test_products_can_publish_different_versions(self):
        self.api.add("AMBER", "1.8.0")
        self.api.add("AmberE", "1.7.4")
        self.assertTrue(self.engine.run(build=lambda engine: None))
        manifest = json.loads((self.root / "public/mirror/index.json").read_text())
        self.assertEqual(list(manifest["products"]["AMBER"]["versions"]), ["1.8.0"])
        self.assertEqual(list(manifest["products"]["AmberE"]["versions"]), ["1.7.4"])

    def test_api_failure_keeps_existing_files_and_last_success(self):
        self.api.add("AMBER")
        self.api.add("AmberE")
        self.engine.run(build=lambda engine: None)
        before = sync.digest(self.root / "public/mirror/amber/1.7.4/AMBER-1.7.4-Setup-x64.exe")
        self.api.failures[sync.PRODUCTS["AMBER"]] = "GITHUB_UNAVAILABLE"
        self.assertFalse(self.engine.run(build=lambda engine: None))
        self.assertEqual(before, sync.digest(self.root / "public/mirror/amber/1.7.4/AMBER-1.7.4-Setup-x64.exe"))
        status = json.loads((self.root / "private/status.json").read_text())
        self.assertIsNotNone(status["components"]["AMBER"]["last_success"])

    def test_drafts_and_prereleases_never_download(self):
        self.api.add()
        self.api.add(version="2.0.0")["draft"] = True
        self.api.add(version="3.0.0")["prerelease"] = True
        self.engine.sync_product("AMBER")
        self.assertEqual(set(self.engine.state["records"]), {"AMBER/1.7.4"})

    def test_semver_not_dates_or_lexical_order(self):
        for v in ("1.9.0", "1.10.0", "1.2.9"):
            self.api.add(version=v)
        self.engine.sync_product("AMBER")
        self.assertEqual(set(self.engine.state["records"]), {"AMBER/1.10.0"})

    def test_missing_digest_no_public_files(self):
        release = self.api.add()
        release["assets"][0]["digest"] = None
        with self.assertRaisesRegex(sync.SyncError, "MISSING_TRUSTED_SHA256"):
            self.engine.sync_release("AMBER", release)
        self.assertFalse((self.root / "public/mirror/amber/1.7.4").exists())

    def test_invalid_newest_does_not_starve_verified_backfill_or_hide_failure(self):
        bad = self.api.add(version='1.7.5')
        bad['assets'][0]['digest'] = None
        self.api.add(version='1.7.4')
        with self.assertRaisesRegex(sync.SyncError,'PRODUCT_SYNC_FAILED'):
            self.engine.sync_product('AMBER')
        self.assertNotIn('AMBER/1.7.5',self.engine.state['records'])
        self.assertIn('AMBER/1.7.4',self.engine.state['records'])

    def test_missing_metadata_digest_also_refused(self):
        release = self.api.add()
        release["assets"][-1]["digest"] = ""
        with self.assertRaises(sync.SyncError):
            self.engine.sync_release("AMBER", release)

    def test_hash_mismatch_never_published(self):
        release = self.api.add()
        asset = release["assets"][0]
        self.api.payloads[asset["browser_download_url"]] = b"x" * asset["size"]
        with self.assertRaisesRegex(sync.SyncError, "DOWNLOAD_INTEGRITY"):
            self.engine.sync_release("AMBER", release)
        self.assertFalse((self.root / "public/mirror/amber/1.7.4").exists())

    def test_wrong_size_never_published(self):
        release = self.api.add()
        release["assets"][0]["size"] += 1
        with self.assertRaisesRegex(sync.SyncError, "DOWNLOAD_INTEGRITY"):
            self.engine.sync_release("AMBER", release)

    def test_same_name_replacement_held_and_original_preserved(self):
        release = self.add_sync()
        original = (self.root / "public/mirror/amber/1.7.4/AMBER-1.7.4-Setup-x64.exe").read_bytes()
        release["assets"][0]["id"] += 1000
        with self.assertRaises(sync.SyncError):
            self.engine.sync_product("AMBER")
        self.engine.manifest()
        index = json.loads((self.root / "public/mirror/index.json").read_text())
        self.assertEqual(index["products"]["AMBER"]["versions"], {})
        self.assertEqual((self.root / "public/mirror/amber/1.7.4/AMBER-1.7.4-Setup-x64.exe").read_bytes(), original)

    def test_failed_first_download_identity_stays_pinned(self):
        release = self.api.add()
        self.api.payloads[release["assets"][0]["browser_download_url"]] = b"bad"
        with self.assertRaises(sync.SyncError):
            self.engine.sync_release("AMBER", release)
        release["assets"][0]["id"] += 999
        with self.assertRaisesRegex(sync.SyncError, "UPSTREAM_ASSET_CHANGED"):
            self.engine.sync_release("AMBER", release)

    def test_upstream_changes_during_download(self):
        release = self.api.add()
        fresh = copy.deepcopy(release)
        fresh["assets"][0]["id"] += 999
        with patch.object(self.api, "release", return_value=fresh):
            with self.assertRaisesRegex(sync.SyncError, "UPSTREAM_CHANGED_DURING_DOWNLOAD"):
                self.engine.sync_release("AMBER", release)

    def test_checksum_metadata_conflict_refused(self):
        release = self.api.add()
        asset = release["assets"][-1]
        payload = self.api.payloads[asset["browser_download_url"]].replace(b"AMBER", b"OTHER")
        self.api.payloads[asset["browser_download_url"]] = payload
        asset["digest"] = "sha256:" + hashlib.sha256(payload).hexdigest()
        with self.assertRaisesRegex(sync.SyncError, "CHECKSUM_METADATA_CONFLICT"):
            self.engine.sync_release("AMBER", release)

    def test_trusted_api_digest_sufficient_without_checksum_asset(self):
        release = self.api.add()
        release["assets"].pop()
        self.engine.sync_release("AMBER", release)
        self.assertTrue((self.root / "public/mirror/amber/1.7.4/SHA256SUMS.mirror.txt").exists())

    def test_unmanaged_directory_not_adopted(self):
        directory = self.root / "public/mirror/amber/1.7.4"
        directory.mkdir(parents=True)
        (directory / "original.txt").write_text("do not change")
        release = self.api.add()
        with self.assertRaisesRegex(sync.SyncError, "UNMANAGED_DESTINATION_EXISTS"):
            self.engine.sync_release("AMBER", release)
        self.assertEqual((directory / "original.txt").read_text(), "do not change")

    def test_local_corruption_held(self):
        self.add_sync()
        (self.root / "public/mirror/amber/1.7.4/AMBER-1.7.4-Setup-x64.exe").write_bytes(b"bad")
        with self.assertRaises(sync.SyncError):
            self.engine.sync_product("AMBER")
        self.assertEqual(self.engine.state["records"]["AMBER/1.7.4"]["status"], "held")

    def test_pending_publication_recovers_after_state_write_failure(self):
        self.add_sync()
        self.engine.state["records"]["AMBER/1.7.4"]["status"] = "pending"
        self.engine.save()
        downloads = self.api.downloads
        sync.Engine(self.config, self.api).sync_product("AMBER")
        self.assertEqual(self.api.downloads, downloads)

    def test_low_disk_does_not_publish(self):
        release = self.api.add()
        with patch.object(self.engine, "space", side_effect=sync.SyncError("INSUFFICIENT_DISK_SPACE")):
            with self.assertRaises(sync.SyncError):
                self.engine.sync_release("AMBER", release)
        self.assertFalse((self.root / "public/mirror/amber/1.7.4").exists())

    def test_sixth_version_plan_only_then_quarantine_and_restore(self):
        for product in sync.PRODUCTS:
            for i in range(1, 7):
                self.add_sync(product, f"1.0.{i}")
        legacy = self.root / "public/mirror/unmanaged.exe"
        legacy.write_bytes(b"not managed")
        plan = self.engine.plan()
        self.assertEqual({c["id"] for c in plan["candidates"]}, {"AMBER/1.0.1", "AmberE/1.0.1"})
        self.assertTrue((self.root / "public/mirror/amber/1.0.1").is_dir())
        self.engine.quarantine(plan["id"])
        self.assertFalse((self.root / "public/mirror/amber/1.0.1").exists())
        self.assertTrue(legacy.exists())
        self.engine.restore("AMBER", "1.0.1")
        self.assertTrue((self.root / "public/mirror/amber/1.0.1").exists())
        self.assertEqual(legacy.read_bytes(), b"not managed")

    def test_page_pins_protect_older_versions(self):
        for i in range(1, 8):
            self.add_sync(version=f"1.0.{i}")
        with patch.object(self.engine, "pins", return_value={"AMBER": {"1.0.1", "1.0.2"}}):
            plan = self.engine.plan()
        self.assertEqual(plan["candidates"], [])
        self.assertEqual(len(plan["protected"]), 2)

    def test_page_pin_change_invalidates_plan(self):
        for i in range(1, 7):
            self.add_sync(version=f"1.0.{i}")
        plan = self.engine.plan()
        with patch.object(self.engine, "pins", return_value={"AMBER": {"1.0.1"}}):
            with self.assertRaisesRegex(sync.SyncError, "PAGE_PINS_OR_INVENTORY_CHANGED"):
                self.engine.quarantine(plan["id"])

    def test_stale_plan_refused(self):
        plan = self.engine.plan()
        self.add_sync()
        with self.assertRaisesRegex(sync.SyncError, "STALE_PLAN"):
            self.engine.quarantine(plan["id"])

    def test_unmanaged_extra_file_blocks_cleanup(self):
        for i in range(1, 7):
            self.add_sync(version=f"1.0.{i}")
        path = self.root / "public/mirror/amber/1.0.1/private-world.zip"
        path.write_bytes(b"keep")
        with self.assertRaisesRegex(sync.SyncError, "UNMANAGED_FILES_PRESENT"):
            self.engine.plan()
        self.assertTrue(path.exists())

    def test_restore_handles_interrupted_quarantine(self):
        self.add_sync()
        r = self.engine.state["records"]["AMBER/1.7.4"]
        r.update(status="quarantining", quarantine="not-yet-moved")
        self.engine.restore("AMBER", "1.7.4")
        self.assertEqual(r["status"], "ready")

    def test_migration_gate(self):
        (self.root / "activation.json").write_text('{}')
        with self.assertRaisesRegex(sync.SyncError, "MIGRATION_NOT_VERIFIED"):
            self.engine.run(build=lambda engine: None)

    def test_lock_excludes_second_process(self):
        path = self.root / "lock"
        with sync.locked(path):
            code = "import sys;sys.path.insert(0,sys.argv[1]);from amber_sync import locked;\nwith locked(__import__('pathlib').Path(sys.argv[2])): pass"
            result = subprocess.run([sys.executable, "-c", code, str(Path(sync.__file__).parent), str(path)],
                                    capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"ALREADY_RUNNING", result.stderr)
        with sync.locked(path):
            pass


class ValidationTests(unittest.TestCase):
    def test_actual_public_174_metadata_matches_supported_schema(self):
        data = json.loads((Path(__file__).parent / "releases-1.7.4.json").read_text())
        self.assertEqual(set(data), set(sync.PRODUCTS))
        for product, release in data.items():
            record = sync.release_record(product, release)
            self.assertEqual(sum(a["installer"] for a in record["files"].values()), 5)
            self.assertEqual(record["excluded"], [product + "-1.7.4-source.zip"])

    def test_paths_and_redirects(self):
        for url in ("http://github.com/x", "https://github.com.evil.test/x", "https://user:password@github.com/x", "https://example.test/x"):
            with self.assertRaises(sync.SyncError):
                sync.trusted_url(url)
        for url in ("https://github.com/a/b", "https://release-assets.githubusercontent.com/file?signature=redacted"):
            self.assertEqual(sync.trusted_url(url), url)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ("../outside", str(root / "absolute")):
                with self.assertRaises(sync.SyncError):
                    sync.confined(root, path)

    def test_bad_metadata(self):
        for mutate in (
            lambda r: r["assets"][0].update(name="../escape.exe"),
            lambda r: r["assets"][0].update(browser_download_url="https://github.com/ayr1k/AmberE/releases/download/v1.7.4/AmberE-1.7.4-Setup-x64.exe"),
            lambda r: r["assets"][0].update(name="AMBER-1.7.5-Setup-x64.exe"),
            lambda r: r["assets"][0].update(size=0),
            lambda r: r["assets"].append(copy.deepcopy(r["assets"][0])),
        ):
            release, _ = fixture()
            mutate(release)
            with self.assertRaises(sync.SyncError):
                sync.release_record("AMBER", release)

    def test_source_excluded_and_additional_supported_types(self):
        release, _ = fixture()
        asset = copy.deepcopy(release["assets"][0])
        asset.update(name="AMBER-1.7.4-source.zip", id=999)
        release["assets"].append(asset)
        self.assertEqual(sync.release_record("AMBER", release)["excluded"], ["AMBER-1.7.4-source.zip"])
        for suffix in ("Setup-arm64.msi", "windows-x64.zip", "mac-universal.dmg", "mac-arm64.pkg", "linux-arm64.AppImage", "linux-x64.rpm", "linux-arm64.tar.gz"):
            self.assertTrue(sync.INSTALLER.fullmatch(suffix))
        self.assertFalse(sync.INSTALLER.fullmatch("source.zip"))

    def test_duplicate_or_nonstandard_stable_tags_refused(self):
        release, _ = fixture()
        with self.assertRaises(sync.SyncError):
            sync.select_releases([release, release])
        release["tag_name"] = "v1.7.4-rc1"
        with self.assertRaises(sync.SyncError):
            sync.select_releases([release])

    def test_api_compare_path_and_traversal_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            api = sync.GitHub(Path(directory))
            response = unittest.mock.MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = b'{"status":"ahead"}'
            response.headers = {}
            compare = f"/repos/{sync.WEBSITE}/compare/{'a' * 40}...{'b' * 40}"
            with patch.object(api, "open", return_value=response) as opened:
                self.assertEqual(api.json(compare), {"status": "ahead"})
                self.assertEqual(opened.call_args.args[0], "https://api.github.com" + compare)
                for path in ("/repos/a/b/../secrets", compare + "/../secrets",
                             compare + "?x=../secrets", compare.replace("...", ".."),
                             compare.replace("a" * 40, "main"),
                             "/repos/a/b/%2e%2e/secrets", "/repos/a/b/%252e%252e/secrets",
                             "/repos/a/b/\\..\\secrets", "/repos/a/b/branches/main#x",
                             "/repos/a/b/branches/main\n", "https://evil.test/repos/a/b"):
                    with self.subTest(path=path):
                        opened.reset_mock()
                        with self.assertRaisesRegex(sync.SyncError, "BAD_API_PATH"):
                            api.json(path)
                        opened.assert_not_called()

    def test_api_pagination_and_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            api = sync.GitHub(Path(directory))
            with patch.object(api, "json", side_effect=[[{}] * 100, [{"id": 1}]]):
                self.assertEqual(len(api.pages("/repos/a/b/releases")), 101)
            with patch.object(api, "json", return_value=[{}] * 100):
                with self.assertRaisesRegex(sync.SyncError, "API_PAGINATION_LIMIT"):
                    api.pages("/repos/a/b/releases")

    def test_304_uses_exact_cache_but_503_never_uses_stale_success(self):
        with tempfile.TemporaryDirectory() as directory:
            api = sync.GitHub(Path(directory))
            response = unittest.mock.MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = b'{"ok":true}'
            response.headers = {"ETag": '"test"'}
            path = "/repos/a/b/branches/main"
            with patch.object(api, "open", return_value=response):
                self.assertEqual(api.json(path), {"ok": True})
            with patch.object(api, "open", side_effect=urllib.error.HTTPError("", 304, "", {}, None)):
                self.assertEqual(api.json(path), {"ok": True})
            with patch.object(api, "open", side_effect=sync.SyncError("GITHUB_UNAVAILABLE")):
                with self.assertRaises(sync.SyncError):
                    api.json(path)

    def test_archive_traversal_and_symlinks_refused(self):
        for name, kind in (("../escape", tarfile.REGTYPE), ("file", tarfile.SYMTYPE)):
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode="w") as archive:
                item = tarfile.TarInfo(name)
                item.type = kind
                archive.addfile(item)
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(sync.SyncError):
                    site.extract_source(data.getvalue(), Path(directory))

    def test_static_missing_reference_and_secret_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text('<script src="/assets/missing.js"></script>')
            with self.assertRaisesRegex(sync.SyncError, "STATIC_REFERENCE_MISSING"):
                site.validate_static(root)
            (root / "index.html").write_text('<p>working</p>')
            (root / "private.key").write_text('fixture')
            with self.assertRaisesRegex(sync.SyncError, "NON_STATIC_OR_SECRET_FILE"):
                site.validate_static(root)


class WorkerProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.engine = sync.Engine({'root':str(self.root / 'runtime'), 'reserve_bytes':0})
        self.results = self.root / 'worker-results'
        self.job_id, self.commit = 'a' * 32, 'b' * 40
        self.job = self.results / self.job_id
        (self.job / 'site').mkdir(parents=True)
        (self.job / 'site/index.html').write_text('<p>fixture</p>')
        self.pins = {p:['1.7.4'] for p in sync.PRODUCTS}
        self.result = {'schema':2,'id':self.job_id,'commit':self.commit,'ok':True,
                       'pins':self.pins,'files':worker.static_hashes(self.job / 'site'),
                       'network':{'install':{'phase':'install','namespace':'net:[1]',
                           'direct_network_blocked':True,'registry_proxy':'registry.npmjs.org:443'},
                           'build':{'phase':'offline','namespace':'net:[2]','direct_network_blocked':True,
                                    'ip_socket_families_blocked':True,'proxy_mounted':False}}}
        self.write_result()

    def write_result(self):
        sync.atomic_json(self.job / 'result.json', self.result)

    def tearDown(self):
        self.temp.cleanup()

    @unittest.skipUnless(os.name=='posix','POSIX preallocation for publication copies')
    def test_verified_worker_result_copied_to_sync_storage(self):
        candidate = worker.accept_result(self.engine,self.results,self.job_id,self.commit,self.pins)
        self.assertTrue(candidate.is_relative_to(self.engine.private))
        self.assertEqual(worker.static_hashes(candidate),self.result['files'])

    @unittest.skipUnless(os.name=='posix','POSIX preallocation for publication copies')
    def test_new_request_can_start_after_prior_service_failure(self):
        requests = self.root / 'requests'
        requests.mkdir()
        self.engine.config.update(builder_requests=str(requests),builder_results=str(self.results))
        source = self.root / 'source'
        (source / 'src').mkdir(parents=True)
        (source / 'src/download-catalog.json').write_text(json.dumps({
            p:{'repo':repo,'version':'1.7.4'} for p,repo in sync.PRODUCTS.items()}))
        (self.job / 'result.json').unlink()  # disposable test fixture only
        calls = []
        def state():
            calls.append(True)
            if len(calls) == 1:
                return 'failed'
            self.write_result()
            return 'inactive'
        with patch('build_worker.uuid.uuid4') as random_id, \
             patch('build_worker.service_state',side_effect=state), \
             patch('build_worker.time.sleep'):
            random_id.return_value.hex = self.job_id
            candidate = worker.request_build(self.engine,source,self.commit)
        self.assertTrue((candidate / 'index.html').exists())

    def test_other_commit_or_job_refused(self):
        for field in ('id','commit'):
            with self.subTest(field=field):
                original = self.result[field]
                self.result[field] = 'c' * len(original)
                self.write_result()
                with self.assertRaisesRegex(sync.SyncError,'BUILD_RESULT_IDENTITY_MISMATCH'):
                    worker.accept_result(self.engine,self.results,self.job_id,self.commit,self.pins)
                self.result[field] = original

    def test_wrong_page_pins_refused(self):
        self.result['pins'] = {'AMBER':['9.0.0']}
        self.write_result()
        with self.assertRaisesRegex(sync.SyncError,'BUILD_RESULT_PINS_MISMATCH'):
            worker.accept_result(self.engine,self.results,self.job_id,self.commit,self.pins)

    def test_tampered_or_extra_output_refused(self):
        (self.job / 'site/index.html').write_text('changed')
        with self.assertRaisesRegex(sync.SyncError,'BUILD_RESULT_INTEGRITY'):
            worker.accept_result(self.engine,self.results,self.job_id,self.commit,self.pins)

    def test_failed_worker_is_not_success_and_cannot_inject_log_text(self):
        for code,expected in [('BUILD_COMMAND_FAILED','BUILD_COMMAND_FAILED'),
                              ('arbitrary response text','INVALID_BUILD_FAILURE_CODE')]:
            self.result.update(ok=False,code=code)
            self.write_result()
            with self.assertRaisesRegex(sync.SyncError,expected):
                worker.accept_result(self.engine,self.results,self.job_id,self.commit,self.pins)

    @unittest.skipUnless(os.name == "posix", "Linux deployment symlinks; CI runs these tests")
    def test_symlink_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target").mkdir()
            (root / "link").symlink_to(root / "target", target_is_directory=True)
            with self.assertRaisesRegex(sync.SyncError, "SYMLINK_REFUSED"):
                sync.confined(root, "link/file")


@unittest.skipUnless(os.name == "posix", "Linux atomic cutover; CI runs these tests")
class DeploymentTests(unittest.TestCase):
    setUp = SyncTests.setUp
    tearDown = SyncTests.tearDown
    add_sync = SyncTests.add_sync
    def create_site(self, commit, version):
        source = self.root / ("source-" + commit)
        (source / "src").mkdir(parents=True)
        (source / "src/download-catalog.json").write_text(json.dumps({
            p: {"repo": repo, "version": version} for p, repo in sync.PRODUCTS.items()}))
        static = source / "dist/client"
        (static / "assets").mkdir(parents=True)
        (static / "index.html").write_text(f'<script src="/assets/{commit}.js"></script>')
        (static / "assets" / (commit + ".js")).write_text('console.log("fixture")')
        site.publish_site(self.engine, source, static, commit)

    def test_cutover_rollback_and_both_page_pins(self):
        self.create_site("a" * 40, "1.0.1")
        self.create_site("b" * 40, "1.0.2")
        self.assertEqual(site.active_pair(self.engine), ("b" * 40, "a" * 40))
        self.assertEqual(self.engine.pins()["AMBER"], {"1.0.1", "1.0.2"})
        self.assertTrue((self.root / "public/active/current/assets" / ("a" * 40 + ".js")).exists())
        site.rollback(self.engine)
        self.assertEqual(site.active_pair(self.engine), ("a" * 40, "b" * 40))
        self.assertTrue(self.engine.state["website"]["paused"])

    def test_failed_build_keeps_pair_and_mirrors(self):
        self.create_site("a" * 40, "1.0.1")
        self.create_site("b" * 40, "1.0.2")
        self.api.add("AMBER")
        self.api.add("AmberE")
        self.assertFalse(self.engine.run(build=lambda engine: (_ for _ in ()).throw(sync.SyncError("BUILD_FAILED"))))
        self.assertEqual(site.active_pair(self.engine), ("b" * 40, "a" * 40))
        self.assertTrue((self.root / "public/mirror/amber/1.7.4").exists())

    def test_generation_and_parent_fsync_precede_active_replace(self):
        self.create_site('a'*40,'1.0.1')
        self.create_site('b'*40,'1.0.2')
        events=[]
        real_sync,real_replace=site.sync_dir,os.replace
        def synced(path):
            events.append(('fsync',Path(path)))
            real_sync(path)
        def replaced(source,target):
            events.append(('replace',Path(target)))
            real_replace(source,target)
        with patch('site_builder.sync_dir',side_effect=synced), \
             patch('site_builder.os.replace',side_effect=replaced):
            site.switch(self.engine,'a'*40,'b'*40)
        generation=events[0][1]
        self.assertEqual(generation.parent,self.engine.public/'site-sets')
        self.assertEqual(events,[('fsync',generation),('fsync',generation.parent),
                                 ('replace',self.engine.public/'active'),('fsync',self.engine.public)])
        self.assertEqual(site.active_pair(self.engine),('a'*40,'b'*40))

    def test_pointer_failure_preserves_current_and_previous(self):
        self.create_site("a" * 40, "1.0.1")
        self.create_site("b" * 40, "1.0.2")
        replace = os.replace
        def fail(src, dst):
            if Path(dst).name == "active":
                raise OSError("simulated power loss before rename")
            return replace(src, dst)
        with patch("site_builder.os.replace", side_effect=fail):
            with self.assertRaises(OSError):
                self.create_site("c" * 40, "1.0.3")
        self.assertEqual(site.active_pair(self.engine), ("b" * 40, "a" * 40))

    def test_actual_page_pins_block_sixth_version_cleanup(self):
        for i in range(1, 7):
            self.add_sync(version=f"1.0.{i}")
        self.create_site("a" * 40, "1.0.1")
        self.create_site("b" * 40, "1.0.2")
        self.assertEqual(self.engine.plan()["candidates"], [])


if __name__ == "__main__":
    unittest.main()
