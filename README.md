# TizenTube TV

A small, **unofficial branding-only fork** of [TizenTube Cobalt](https://github.com/reisxd/TizenTubeCobalt).
The installed app displays **YouTube**, with the familiar icon and Android TV
launcher tile. This is **not an official Google/YouTube app**.

## Downloads

[Download the latest release](https://github.com/djdoolky76/TizenTube-TV/releases/latest)

| APK | Architecture |
| --- | --- |
| `TizenTube-TV-arm32.apk` | 32-bit ARM (`armeabi-v7a`), including the tested Mi Box |
| `TizenTube-TV-arm64.apk` | 64-bit ARM (`arm64-v8a`) |

Choose according to your **Android userspace ABI**, not just the CPU's advertised
capabilities. Android 7.0+ is required by the pinned upstream baseline.

## What changes—and what does not

- App label: **YouTube**.
- All five launcher-icon density variants and all five TV-banner variants replaced.
- Package remains **`io.gh.reisxd.tizentube.cobalt`**.
- DEX code, native libraries, assets, resource table, permissions, version and
  authentication/playback behavior are preserved from upstream.
- Existing upstream features, such as SponsorBlock, DeArrow and speed controls,
  remain upstream implementations. No Morphe patches or MicroG are added.

The release pipeline **rebrands pinned upstream release APKs**. It does not
compile the entire Cobalt/Chromium engine, and it does not claim that this fork's
current source checkout produced upstream's binaries. Source branding files
are updated too, for consistency with any future full source builds.

Input APK hashes are pinned in [`branding/upstream.json`](branding/upstream.json).
Every build checks that only the manifest label, icon/banner files and signing
metadata differ. Each release includes verification reports and `SHA256SUMS.txt`.
Network-loaded content and upstream services can still change independently.

## Installation and updates

Sideload the appropriate APK using a file manager or ADB:

```sh
adb install --no-incremental -r TizenTube-TV-arm32.apk
```

Stock YouTube uses a different package and is not replaced. Official TizenTube
uses the **same package but a different signing key**: switching from it normally
requires uninstalling it first, clearing its local sign-in/settings. Back up
settings if needed. Subsequent releases from this fork use one persistent key
and can update in place. The initial branded test build on the Mi Box uses
that same key.

**The upstream in-app updater is unchanged.** Its upstream APKs cannot update
this differently signed fork. Get updates from this repository's Releases,
not the upstream in-app updater.

## Automated builds and releases

- Relevant pushes to `main`: tests and signed ARM32 + ARM64 artifacts.
- Pull requests: tests only; no signing secrets are exposed.
- **Actions → TizenTube TV APKs → Run workflow**: build both variants manually.
- Push the tag specified by `release_tag` in `branding/upstream.json` to build
  and publish both variants together. Current baseline: **`v2.0.3-tv.1`**.
- [Build and signing instructions](branding/BUILDING.md).

The initial ARM32 build was tested on a device reporting **MIBOX4, Android 12**:
QR sign-in, video/audio playback, remote navigation and launcher branding worked.
ARM64 receives the same automated payload/signature checks, but has **not been
tested on physical ARM64 hardware**.

## Credits and notices

All player functionality is credited to TizenTube Cobalt and its upstream
contributors. [Original project README](branding/UPSTREAM_README.md) ·
[Branding notices](branding/NOTICE.md) · [Upstream license](LICENSE).

YouTube names and artwork belong to Google; no trademark permission or
endorsement is implied. Existing upstream and third-party notices are retained.
