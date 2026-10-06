# insitesoftware.github.io

Static [Terraform provider registry](https://developer.hashicorp.com/terraform/internals/provider-registry-protocol)
served by GitHub Pages. Temporary home for our patched fork of the Mailgun
provider (rate limiting and 429 retry) until upstream merges the fix.

```hcl
terraform {
  required_providers {
    mailgun = {
      source  = "insitesoftware.github.io/insitesoftware/mailgun"
      version = "0.10.1-ratelimit.1" # exact pin: prerelease versions never match ranges
    }
  }
}
```

- Provider source: <https://github.com/InsiteSoftware/terraform-provider-mailgun>
- Signing key: `keys/signing-key.asc`, fingerprint
  `BEC2B706DE42FC9A8AB811D1CD2006D7A3D26E2D`. The private key and passphrase are in
  Vault at `kv/internal/b2bcommerce/github-mailgun-provider-signing-release`.

## Adding a release

1. Tag the provider repo (`vX.Y.Z-...`); its release workflow publishes the zips,
   `SHA256SUMS` and `SHA256SUMS.sig`.
2. Here, run `scripts/add_version.py X.Y.Z-...`. It downloads the checksums, verifies
   the signature against `keys/signing-key.asc` and writes the registry files.
3. Commit and push. Pages publishes within a minute or two.

`.nojekyll` must stay: without it Jekyll drops the `.well-known` directory.
