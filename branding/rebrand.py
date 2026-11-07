# SPDX-License-Identifier: BSD-3-Clause
"""Brand pinned upstream APKs without rebuilding or modifying runtime code."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from axml import rename_manifest_label

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path(__file__).with_name("upstream.json")
RESOURCES = ROOT / "cobalt/shell/android/java/res"
DENSITIES = {160: "mdpi", 240: "hdpi", 320: "xhdpi", 480: "xxhdpi", 640: "xxxhdpi"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(*args, capture=False):
    result = subprocess.run(
        [str(arg) for arg in args], check=True, text=True,
        encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    return result.stdout if capture else None


def executable(tools, name):
    return tools / (name + (".exe" if os.name == "nt" else ""))


def icon_paths(badging):
    return {int(d): path for d, path in re.findall(
        r"^application-icon-(\d+):'([^']+)'", badging, re.MULTILINE
    )}


def banner_path(badging):
    match = re.search(r"^application:.* banner='([^']+)'", badging, re.MULTILINE)
    if not match:
        raise RuntimeError("Missing TV banner")
    return match.group(1)


def banner_resource_paths(names):
    return {n for n in names if re.fullmatch(r"res/drawable(?:-[^/]+)?/app_banner(?:\.png)?", n)}


def is_signature_metadata(name):
    return name == "META-INF/MANIFEST.MF" or bool(re.fullmatch(
        r"META-INF/[^/]+\.(SF|RSA|DSA|EC)", name, re.IGNORECASE
    ))


def verify_payloads(source, output, allowed):
    with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
        before_names, after_names = set(before.namelist()), set(after.namelist())
        if len(before_names) != len(before.infolist()) or len(after_names) != len(after.infolist()):
            raise RuntimeError("Duplicate APK entries")
        membership_changes = before_names ^ after_names
        if any(not is_signature_metadata(n) for n in membership_changes):
            raise RuntimeError("Unexpected ZIP membership change")
        changed, preserved = [], 0
        for name in sorted(before_names & after_names):
            same = before.read(name) == after.read(name)
            if not same and name not in allowed and not is_signature_metadata(name):
                raise RuntimeError(f"Unexpected payload modification: {name}")
            if same:
                preserved += 1
            else:
                changed.append(name)
        if before.read("resources.arsc") != after.read("resources.arsc"):
            raise RuntimeError("Resource table changed")
        return {"changed_payloads": changed, "unchanged_payload_count": preserved,
                "signature_metadata_changes": sorted(membership_changes)}


def read_png(path, expected_hash):
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or digest(data) != expected_hash:
        raise RuntimeError(f"Branding asset missing, changed, or invalid: {path}")
    return data


def build(args):
    config = json.loads(args.config.read_text(encoding="utf-8"))
    variant = config["variants"][args.variant]
    source = args.input.resolve()
    if file_digest(source) != variant["sha256"]:
        raise RuntimeError("Upstream APK SHA-256 mismatch; refusing unreviewed input")
    if not args.keystore.is_file() or not os.environ.get(args.ks_pass_env):
        raise RuntimeError("Persistent signing key/password missing; never create a temporary release key")

    tools = args.build_tools.resolve()
    aapt, zipalign = executable(tools, "aapt"), executable(tools, "zipalign")
    original_badging = run(aapt, "dump", "badging", source, capture=True)
    expected_package = f"package: name='{config['package']}' versionCode='{config['version_code']}' versionName='{config['version_name']}'"
    if expected_package not in original_badging or "application-label:'TizenTube'" not in original_badging:
        raise RuntimeError("Unexpected upstream package/version/label")
    if f"native-code: '{variant['abi']}'" not in original_badging:
        raise RuntimeError("APK architecture does not match requested variant")
    icons = icon_paths(original_badging)
    if set(icons) != set(DENSITIES):
        raise RuntimeError("Unexpected icon density mapping")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    artifact = f"TizenTube-TV-{args.variant}.apk"
    output = args.output_dir / artifact
    with tempfile.TemporaryDirectory(prefix="tizentube-tv-") as temp:
        work = Path(temp)
        unsigned, aligned = work / "unsigned.apk", work / "aligned.apk"
        with zipfile.ZipFile(source) as original:
            banners = banner_resource_paths(original.namelist())
            if banner_path(original_badging) not in banners or len(banners) != 5:
                raise RuntimeError("Unexpected TV banner variants")
            replacements = {"AndroidManifest.xml": rename_manifest_label(original.read("AndroidManifest.xml"))}
            for density, qualifier in DENSITIES.items():
                replacements[icons[density]] = read_png(
                    RESOURCES / f"mipmap-{qualifier}/ic_app.png", config["icon_sha256"][qualifier]
                )
            banner = read_png(RESOURCES / "drawable-xhdpi/app_banner.png", config["banner_sha256"])
            for path in banners:
                replacements[path] = banner
            with zipfile.ZipFile(unsigned, "w") as result:
                for info in original.infolist():
                    if not is_signature_metadata(info.filename):
                        value = replacements.get(info.filename)
                        result.writestr(info, original.read(info.filename) if value is None else value)
        run(zipalign, "-P", "16", "-f", "4", unsigned, aligned)
        signer = tools / "lib/apksigner.jar"
        run("java", "-jar", signer, "sign", "--ks", args.keystore.resolve(),
            "--ks-key-alias", args.ks_alias, "--ks-pass", f"env:{args.ks_pass_env}",
            "--key-pass", f"env:{args.ks_pass_env}", "--out", output, aligned)
        signature = run("java", "-jar", signer, "verify", "--verbose", "--print-certs", output, capture=True)
        cert = re.search(r"Signer #1 certificate SHA-256 digest: ([0-9a-f]+)", signature)
        if not cert or cert.group(1) != config["signing_certificate_sha256"]:
            raise RuntimeError("Signing certificate does not match the installed/tested build")
        run(zipalign, "-c", "-P", "16", "4", output)

    result_badging = run(aapt, "dump", "badging", output, capture=True)
    if expected_package not in result_badging or "application-label:'YouTube'" not in result_badging:
        raise RuntimeError("Output package/version/label mismatch")
    if f"native-code: '{variant['abi']}'" not in result_badging or icon_paths(result_badging) != icons:
        raise RuntimeError("Output ABI or icon resource mapping changed")
    if banner_path(result_badging) != banner_path(original_badging):
        raise RuntimeError("Banner reference changed")
    before = run(aapt, "dump", "xmltree", source, "AndroidManifest.xml", capture=True)
    after = run(aapt, "dump", "xmltree", output, "AndroidManifest.xml", capture=True)
    if before.replace('"TizenTube"', '"YouTube"') != after:
        raise RuntimeError("Manifest changed beyond the visible app label")
    payloads = verify_payloads(source, output, set(replacements))
    with zipfile.ZipFile(output) as result:
        for name, expected in replacements.items():
            if result.read(name) != expected:
                raise RuntimeError(f"Incorrect output branding: {name}")
    report = {
        "release_tag": config["release_tag"], "upstream_tag": config["upstream_tag"],
        "upstream_url": variant["url"], "upstream_sha256": variant["sha256"],
        "output_sha256": file_digest(output), "artifact": artifact,
        "variant": args.variant, "abi": variant["abi"], "package": config["package"],
        "display_label": "YouTube", "version_name": config["version_name"],
        "version_code": config["version_code"], "signing_certificate_sha256": cert.group(1),
        "dex_native_assets_unchanged": True, "resource_table_unchanged": True,
        "manifest_only_label_changed": True, "banner_variants_replaced": sorted(banners),
        "signature_verification": signature, **payloads,
    }
    report_path = args.output_dir / f"TizenTube-TV-{args.variant}.verification.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {args.variant}: {output}")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--variant", choices=["arm32", "arm64"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--build-tools", type=Path, required=True)
    parser.add_argument("--keystore", type=Path, required=True)
    parser.add_argument("--ks-alias", default="branding")
    parser.add_argument("--ks-pass-env", default="TIZENTUBE_KEY_PASSWORD")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "branding/output")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
