#!/usr/bin/env python3
"""Add a provider release to this static Terraform registry.

Implements the Terraform Provider Registry Protocol
(https://developer.hashicorp.com/terraform/internals/provider-registry-protocol)
as static files served by GitHub Pages.

Usage:
    scripts/add_version.py 0.10.1-ratelimit.1

Downloads the release's SHA256SUMS and SHA256SUMS.sig from GitHub, verifies the
signature with gpg against keys/signing-key.asc, then writes:

    .well-known/terraform.json
    v1/providers/<namespace>/<type>/versions                 (merged, not replaced)
    v1/providers/<namespace>/<type>/<version>/download/<os>/<arch>

Run from anywhere; paths are resolved relative to the repo root.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

# Source GitHub repo whose releases hold the zips, SHA256SUMS and signature.
RELEASE_REPO = "InsiteSoftware/terraform-provider-mailgun"
PROJECT_NAME = "terraform-provider-mailgun"

# Provider address: insitesoftware.github.io/<NAMESPACE>/<TYPE>. Terraform
# lowercases these before requesting, and Pages paths are case-sensitive.
NAMESPACE = "insitesoftware"
TYPE = "mailgun"

# Plugin protocol. The provider is terraform-plugin-framework only and serves
# tf6server (see main.go), so this is 6.0.
PROTOCOLS = ["6.0"]

KEY_FILE = "keys/signing-key.asc"
KEY_ID = "CD2006D7A3D26E2D"  # long ID of BEC2B706DE42FC9A8AB811D1CD2006D7A3D26E2D
KEY_SOURCE = "InsiteSoftware"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVIDER_DIR = os.path.join(ROOT, "v1", "providers", NAMESPACE, TYPE)


def fetch(url):
    with urllib.request.urlopen(url) as resp:
        return resp.read()


def verify_signature(sums, sig):
    """Fail unless sig is a valid signature of sums by KEY_FILE."""
    with tempfile.TemporaryDirectory() as home:
        os.chmod(home, 0o700)
        env = dict(os.environ, GNUPGHOME=home)
        subprocess.run(["gpg", "--batch", "--quiet", "--import", os.path.join(ROOT, KEY_FILE)],
                       env=env, check=True, capture_output=True)
        sums_path, sig_path = os.path.join(home, "sums"), os.path.join(home, "sums.sig")
        with open(sums_path, "wb") as f:
            f.write(sums)
        with open(sig_path, "wb") as f:
            f.write(sig)
        res = subprocess.run(["gpg", "--batch", "--status-fd", "1", "--verify", sig_path, sums_path],
                             env=env, capture_output=True, text=True)
        if res.returncode != 0 or "[GNUPG:] VALIDSIG" not in res.stdout:
            sys.exit(f"signature verification failed:\n{res.stderr}")


def parse_sums(sums, version):
    """Return {(os, arch): (filename, sha256)} for each zip in SHA256SUMS."""
    pattern = re.compile(rf"^{re.escape(PROJECT_NAME)}_{re.escape(version)}_([a-z0-9]+)_([a-z0-9]+)\.zip$")
    platforms = {}
    for line in sums.decode().splitlines():
        if not line.strip():
            continue
        shasum, filename = line.split()
        m = pattern.match(filename)
        if m:
            platforms[(m.group(1), m.group(2))] = (filename, shasum)
    if not platforms:
        sys.exit("no provider zips found in SHA256SUMS")
    return platforms


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def version_key(v):
    # Rough semver ordering, enough to keep the versions file tidy; Terraform
    # does its own sorting.
    core, _, pre = v.partition("-")
    return [int(x) for x in core.split(".")], pre == "", pre


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    version = sys.argv[1].lstrip("v")
    tag = f"v{version}"

    base = f"https://github.com/{RELEASE_REPO}/releases/download/{tag}"
    sums_name = f"{PROJECT_NAME}_{version}_SHA256SUMS"
    sums_url, sig_url = f"{base}/{sums_name}", f"{base}/{sums_name}.sig"

    sums, sig = fetch(sums_url), fetch(sig_url)
    verify_signature(sums, sig)
    platforms = parse_sums(sums, version)

    with open(os.path.join(ROOT, KEY_FILE)) as f:
        ascii_armor = f.read()

    write_json(os.path.join(ROOT, ".well-known", "terraform.json"), {"providers.v1": "/v1/providers/"})

    for (os_name, arch), (filename, shasum) in sorted(platforms.items()):
        write_json(os.path.join(PROVIDER_DIR, version, "download", os_name, arch), {
            "protocols": PROTOCOLS,
            "os": os_name,
            "arch": arch,
            "filename": filename,
            "download_url": f"{base}/{filename}",
            "shasums_url": sums_url,
            "shasums_signature_url": sig_url,
            "shasum": shasum,
            "signing_keys": {
                "gpg_public_keys": [{
                    "key_id": KEY_ID,
                    "ascii_armor": ascii_armor,
                    "trust_signature": "",
                    "source": KEY_SOURCE,
                    "source_url": None,
                }],
            },
        })

    versions_path = os.path.join(PROVIDER_DIR, "versions")
    versions = {"versions": []}
    if os.path.exists(versions_path):
        with open(versions_path) as f:
            versions = json.load(f)
    versions["versions"] = [v for v in versions["versions"] if v["version"] != version]
    versions["versions"].append({
        "version": version,
        "protocols": PROTOCOLS,
        "platforms": [{"os": o, "arch": a} for o, a in sorted(platforms)],
    })
    versions["versions"].sort(key=lambda v: version_key(v["version"]))
    write_json(versions_path, versions)

    print(f"added {NAMESPACE}/{TYPE} {version}: {len(platforms)} platforms, signature verified")


if __name__ == "__main__":
    main()
