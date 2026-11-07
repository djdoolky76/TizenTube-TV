## Branding-only baseline, based on TizenTube Cobalt v2.0.3

- Display name: **YouTube**.
- Familiar YouTube app icon and Android TV launcher banner (all density variants).
- Original TizenTube package: `io.gh.reisxd.tizentube.cobalt`.
- Upstream player code, native libraries, assets, permissions, authentication
  and playback implementation are unchanged; this is verified during packaging.
- Independently signed with the same persistent key as the initial Mi Box test.

### Downloads

- **TizenTube-TV-arm32.apk** — `armeabi-v7a` / 32-bit Android.
- **TizenTube-TV-arm64.apk** — `arm64-v8a` / 64-bit Android.
- Requires Android 7.0+. Choose based on the OS ABI, not just the CPU model.

ARM32 was tested on a Mi Box reporting MIBOX4 / Android 12: QR sign-in,
video/audio playback, remote controls, app name and launcher artwork work.
ARM64 is package/signature/payload-verified, **not hardware-tested**.

### Important

This is **not an official Google/YouTube release**. All app functionality comes
from upstream TizenTube Cobalt; this release rebrands upstream release binaries,
not a new full-engine compilation. Check the attached verification reports
and SHA256SUMS.txt for provenance and integrity.

Official TizenTube uses the same package with another signing certificate, so
switching from upstream requires uninstalling it first and signing in again.
Existing builds signed by this fork can update in place. Stock YouTube remains
separate. Do not use TizenTube's upstream in-app updater for this fork; install
future updates from this repository's Releases.
