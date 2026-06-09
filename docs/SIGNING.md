# Code signing & notarization

By default iPlus ships **unsigned** installers — users click through a Gatekeeper
(macOS) or SmartScreen (Windows) warning on first launch. To remove those warnings you
need code-signing certificates. **The release CI is already wired for this**: it signs
and notarizes automatically the moment the secrets below exist, and falls back to an
ad-hoc/unsigned build when they don't (so nothing breaks in the meantime).

> Updater signing (minisign, `TAURI_SIGNING_PRIVATE_KEY`) is a *separate* thing that's
> already configured — it's what lets auto-update verify downloads. Code signing below is
> about the OS trusting the installer itself.

---

## macOS — Developer ID + notarization

**Prerequisite:** an [Apple Developer Program](https://developer.apple.com/programs/) membership ($99/year).

### 1. Create a "Developer ID Application" certificate
- developer.apple.com → **Certificates, IDs & Profiles** → **+** → **Developer ID Application**.
- Follow the CSR steps, download the cert, and double-click to add it to **Keychain Access**.

### 2. Export it as a `.p12`
- In Keychain Access, find the cert → right-click → **Export** → `.p12` format → set a password.
- Base64-encode it for GitHub:
  ```bash
  base64 -i Certificates.p12 | pbcopy   # now in your clipboard
  ```

### 3. Create an app-specific password (for notarization)
- appleid.apple.com → **Sign-In and Security** → **App-Specific Passwords** → generate one.

### 4. Find your Team ID
- developer.apple.com → **Membership** → "Team ID" (10 characters).

### 5. Add these GitHub repo secrets
*(Settings → Secrets and variables → Actions → New repository secret)*

| Secret | Value |
|---|---|
| `APPLE_CERTIFICATE` | the base64 string from step 2 |
| `APPLE_CERTIFICATE_PASSWORD` | the `.p12` password from step 2 |
| `APPLE_SIGNING_IDENTITY` | `Developer ID Application: Your Name (TEAMID)` |
| `APPLE_ID` | your Apple ID email |
| `APPLE_PASSWORD` | the app-specific password from step 3 |
| `APPLE_TEAM_ID` | your Team ID from step 4 |
| `KEYCHAIN_PASSWORD` | any random string (a throwaway keychain password) |

### 6. Cut a release
```bash
git tag v0.4.1 && git push origin v0.4.1
```
CI detects `APPLE_CERTIFICATE`, imports it into a temporary keychain, and tauri-action
signs **and** notarizes the `.app`/`.dmg`. No code change needed.

### 7. Verify
```bash
codesign --verify --deep --strict --verbose=2 /Applications/iPlus.app
spctl -a -t exec -vv /Applications/iPlus.app
# → "accepted, source=Notarized Developer ID"
```

> `tauri.conf.json` already sets `hardenedRuntime: true` and the entitlements needed for the
> PyInstaller sidecar (`disable-library-validation`), so notarization passes. You can leave
> `signingIdentity: "-"` — `APPLE_SIGNING_IDENTITY` overrides it in CI.

---

## Windows

Unsigned `.exe`/`.msi` trigger SmartScreen. Options, cheapest-effort first:

- **Azure Trusted Signing** (pay-as-you-go, no hardware token) — recommended for OSS. Add
  the [`azure/trusted-signing-action`](https://github.com/Azure/trusted-signing-action) and
  point `scripts/sign-windows.ps1` (currently a no-op) at it.
- **An OV/EV code-signing certificate** from a CA — add `WINDOWS_CERTIFICATE` (+ password)
  secrets and implement `signtool sign` in `scripts/sign-windows.ps1`.

The CI `signCommand` already calls `scripts/sign-windows.ps1`; today it's a documented
no-op (unsigned). Fill it in once you have a certificate.

---

## How the CI is wired (for reviewers)

In `.github/workflows/release.yml`:
- A job-level `HAS_APPLE_CERT: ${{ secrets.APPLE_CERTIFICATE != '' }}` flag.
- An **"Import Apple signing certificate"** step that runs **only** on macOS **and only** when
  that flag is true. It imports the cert and exports `APPLE_SIGNING_IDENTITY` / `APPLE_ID` /
  `APPLE_PASSWORD` / `APPLE_TEAM_ID` to `$GITHUB_ENV` for tauri-action.
- When no cert is configured the step is skipped, no `APPLE_*` env is set, and the build is
  ad-hoc — identical to releases v0.1.0–v0.4.0.

This keeps the unsigned path working while making signing a pure "add secrets and re-tag" op.
