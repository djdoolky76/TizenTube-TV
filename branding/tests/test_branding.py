# SPDX-License-Identifier: BSD-3-Clause
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from axml import rename_manifest_label, write_length
from rebrand import (CONFIG, RESOURCES, ROOT, banner_path, banner_resource_paths,
                     file_digest, icon_paths, is_signature_metadata, verify_payloads)


def compiled_xml(strings, utf8):
    records, offsets = bytearray(), []
    for text in strings:
        offsets.append(len(records))
        encoded = text.encode("utf-8" if utf8 else "utf-16-le")
        records.extend(write_length(len(text.encode("utf-16-le")) // 2, utf8))
        if utf8:
            records.extend(write_length(len(encoded), True))
        records.extend(encoded + (b"\0" if utf8 else b"\0\0"))
    records.extend(b"\0" * (-len(records) % 4))
    start = 28 + len(strings) * 4
    pool = struct.pack("<HHIIIIII", 1, 28, start + len(records), len(strings), 0, 0x100 if utf8 else 0, start, 0)
    pool += struct.pack(f"<{len(strings)}I", *offsets) + records
    tail = struct.pack("<HHI", 0x102, 8, 8)
    return struct.pack("<HHI", 3, 8, 8 + len(pool) + len(tail)) + pool + tail


class ManifestTests(unittest.TestCase):
    def check_rename(self, utf8):
        original = compiled_xml(["unchanged", "TizenTube", "é" * 130, "😀"], utf8)
        expected = compiled_xml(["unchanged", "YouTube", "é" * 130, "😀"], utf8)
        self.assertEqual(rename_manifest_label(original), expected)

    def test_utf8_pool(self):
        self.check_rename(True)

    def test_utf16_pool(self):
        self.check_rename(False)

    def test_missing_label(self):
        with self.assertRaises(RuntimeError):
            rename_manifest_label(compiled_xml(["other"], True))

    def test_duplicate_label(self):
        with self.assertRaises(RuntimeError):
            rename_manifest_label(compiled_xml(["TizenTube", "TizenTube"], True))

    def test_bad_file_size(self):
        with self.assertRaises(RuntimeError):
            rename_manifest_label(compiled_xml(["TizenTube"], True) + b"extra")

    def test_zero_size_chunk(self):
        data = bytearray(compiled_xml(["TizenTube"], True))
        struct.pack_into("<HHI", data, 8, 5, 0, 0)
        with self.assertRaises(RuntimeError):
            rename_manifest_label(bytes(data))

    def test_styles_are_rejected(self):
        data = bytearray(compiled_xml(["TizenTube"], True))
        struct.pack_into("<I", data, 8 + 12, 1)
        with self.assertRaises(RuntimeError):
            rename_manifest_label(bytes(data))


class ResourceTests(unittest.TestCase):
    def test_banner_reference(self):
        self.assertEqual(banner_path("application: label='YouTube' icon='res/icon' banner='res/dN.png'\n"), "res/dN.png")

    def test_missing_banner(self):
        with self.assertRaises(RuntimeError):
            banner_path("application: label='YouTube' icon='res/icon'\n")

    def test_all_banner_variants(self):
        variants = {"res/drawable/app_banner", "res/drawable-hdpi-v4/app_banner",
                    "res/drawable-xhdpi-v4/app_banner", "res/drawable-xxhdpi-v4/app_banner",
                    "res/drawable-xxxhdpi-v4/app_banner"}
        self.assertEqual(banner_resource_paths(variants | {"assets/app_banner", "res/drawable/other"}), variants)

    def test_icon_paths(self):
        self.assertEqual(icon_paths("application-icon-160:'res/a'\napplication-icon-320:'res/b'\n"), {160: "res/a", 320: "res/b"})

    def test_signature_filter_preserves_notices(self):
        for name in ("META-INF/MANIFEST.MF", "META-INF/CERT.SF", "META-INF/CERT.RSA"):
            self.assertTrue(is_signature_metadata(name))
        for name in ("META-INF/LICENSE", "META-INF/NOTICE", "assets/LICENSE"):
            self.assertFalse(is_signature_metadata(name))

    def test_pinned_source_assets(self):
        config = json.loads(CONFIG.read_text())
        for qualifier, expected in config["icon_sha256"].items():
            self.assertEqual(file_digest(RESOURCES / f"mipmap-{qualifier}/ic_app.png"), expected)
            self.assertEqual(file_digest(RESOURCES / f"drawable-{qualifier}/app_banner.png"), config["banner_sha256"])

    def test_source_manifest_label(self):
        manifest = ROOT / "cobalt/shell/android/shell_apk/AndroidManifest.xml.jinja2"
        self.assertIn('android:label="{% block application_label %}YouTube{% endblock %}"', manifest.read_text())

    def test_pinned_variants(self):
        config = json.loads(CONFIG.read_text())
        self.assertEqual(set(config["variants"]), {"arm32", "arm64"})
        self.assertEqual(config["variants"]["arm32"]["abi"], "armeabi-v7a")
        self.assertEqual(config["variants"]["arm64"]["abi"], "arm64-v8a")
        for spec in config["variants"].values():
            self.assertRegex(spec["sha256"], r"^[0-9a-f]{64}$")
            self.assertIn(f"/releases/download/{config['upstream_tag']}/", spec["url"])


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source.apk"
        self.output = Path(self.temp.name) / "output.apk"
        self.original = {"AndroidManifest.xml": b"old", "resources.arsc": b"table",
                         "classes.dex": b"dex", "lib/armeabi-v7a/libcobalt.so": b"native",
                         "assets/NOTICE": b"notice", "META-INF/NOTICE": b"another notice",
                         "res/drawable/app_banner": b"banner"}
        self.write(self.source, self.original)

    def write(self, path, entries):
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, data)

    def test_only_allowed_branding_change(self):
        self.write(self.output, {**self.original, "AndroidManifest.xml": b"new"})
        result = verify_payloads(self.source, self.output, {"AndroidManifest.xml"})
        self.assertEqual(result["changed_payloads"], ["AndroidManifest.xml"])

    def test_runtime_changes_rejected(self):
        for name in ("classes.dex", "resources.arsc", "lib/armeabi-v7a/libcobalt.so", "assets/NOTICE", "META-INF/NOTICE"):
            with self.subTest(name=name):
                self.write(self.output, {**self.original, name: b"changed"})
                with self.assertRaises(RuntimeError):
                    verify_payloads(self.source, self.output, {"AndroidManifest.xml"})

    def test_missing_runtime_file_rejected(self):
        self.write(self.output, {k: v for k, v in self.original.items() if k != "classes.dex"})
        with self.assertRaises(RuntimeError):
            verify_payloads(self.source, self.output, set())

    def test_new_runtime_file_rejected(self):
        self.write(self.output, {**self.original, "classes2.dex": b"extra"})
        with self.assertRaises(RuntimeError):
            verify_payloads(self.source, self.output, set())

    def test_new_signature_metadata_allowed(self):
        self.write(self.output, {**self.original, "META-INF/BRANDING.RSA": b"certificate"})
        verify_payloads(self.source, self.output, set())


if __name__ == "__main__":
    unittest.main()
