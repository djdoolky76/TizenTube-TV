# SPDX-License-Identifier: BSD-3-Clause
"""Download only a pinned upstream release asset, checking its full SHA-256."""

import argparse
import json
from pathlib import Path
import shutil
import tempfile
import urllib.request

from rebrand import CONFIG, file_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["arm32", "arm64"], required=True)
    parser.add_argument("--output-dir", type=Path, default=CONFIG.parent / "downloads")
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    variant = config["variants"][args.variant]
    expected_url = f"https://github.com/{config['repository']}/releases/download/{config['upstream_tag']}/{variant['asset']}"
    if variant["url"] != expected_url:
        raise RuntimeError("Unexpected download URL")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / variant["asset"]
    if output.exists():
        if file_digest(output) != variant["sha256"]:
            raise RuntimeError(f"Existing input has a wrong digest; review it manually: {output}")
    else:
        with tempfile.TemporaryDirectory(prefix="upstream-", dir=args.output_dir) as temp:
            partial = Path(temp) / variant["asset"]
            request = urllib.request.Request(variant["url"], headers={"User-Agent": "TizenTube-TV-builder"})
            with urllib.request.urlopen(request, timeout=180) as response, partial.open("wb") as target:
                shutil.copyfileobj(response, target)
            if file_digest(partial) != variant["sha256"]:
                raise RuntimeError("Downloaded upstream asset SHA-256 mismatch")
            partial.replace(output)
    print(f"Verified upstream APK: {output}")


if __name__ == "__main__":
    main()
