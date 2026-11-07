# Branding build and release guide

## Requirements

- Python 3.12+ (standard library only).
- Java 17+ (`java` on PATH).
- Android SDK build-tools **36.0.0** (`aapt`, `zipalign`, `lib/apksigner.jar`).
- The persistent signing key and password—not a newly generated key per build.

The full Chromium checkout is not necessary for release repackaging. A shallow,
blob-filtered sparse checkout of `branding` and
`cobalt/shell/android/java/res` is sufficient.

## Local build

Download a hash-verified baseline:

```sh
python branding/download.py --variant arm32
python branding/download.py --variant arm64
python -m unittest discover -s branding/tests -v
```

Set `TIZENTUBE_KEY_PASSWORD` privately in your environment. Never put the password
on a command line or commit the signing key/password. Then build, for example:

```sh
python branding/rebrand.py \
  --variant arm32 \
  --input branding/downloads/cobalt-arm.apk \
  --build-tools /path/to/android-sdk/build-tools/36.0.0 \
  --keystore /private/path/branding.p12
```

For ARM64 use `--variant arm64` and `cobalt-arm64.apk`. On Windows the same
arguments work with Windows paths (use PowerShell backticks for multiline commands).
Signing alias defaults to `branding`. Outputs go into `branding/output/`.

The checked signing certificate fingerprint must match
`branding/upstream.json`; this prevents accidentally releasing builds that
cannot update the already installed app. `.local/`, downloads, APK outputs,
keystores and password files must not be committed.

## Actions secrets

Create these **repository Actions secrets**, not plaintext variables:

| Secret | Value |
| --- | --- |
| `TIZENTUBE_KEYSTORE_BASE64` | Base64 of the existing PKCS#12 signing key |
| `TIZENTUBE_KEY_PASSWORD` | Its existing password |

The owner approved using the same private key as the tested Mi Box install.
Keep a separate private backup: GitHub does not let you retrieve secret values.
The workflow never creates a replacement key, never signs pull-request code,
and deletes the runner's temporary key after signing. Reports contain the
public certificate fingerprint, not the private key or password.

## Publishing

1. Update/review code, assets and pinned hashes; increment `release_tag` for a
   new fork release. `version_name`/`version_code` intentionally remain upstream's.
2. Push to `main` and wait for both architecture builds to pass.
3. Tag that reviewed commit with the exact `release_tag`, e.g.:

   ```sh
   git tag v2.0.3-tv.1
   git push origin v2.0.3-tv.1
   ```

4. Actions builds both variants, verifies uploaded artifact hashes, creates a
   draft GitHub Release with both APKs/reports/checksums/notices, then publishes it.
   It refuses to overwrite an existing release. Failed draft publication can be
   reviewed manually before retrying; do not silently replace published APKs.

For a new upstream version, explicitly update the release URLs, SHA-256 digests,
version metadata, layout assumptions and release notes, then retest on hardware.
The workflow does **not** blindly pull a changing `latest` APK.

The existing inherited Cobalt workflows remain available, but this fork's normal
release path is **TizenTube TV APKs**, not those full engine-build workflows.
