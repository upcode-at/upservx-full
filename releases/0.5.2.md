## Release v0.5.2 - Security Patch

**Release Date:** 2026-05-19

### What's New in UpservX v0.5.2

This is a security patch release addressing multiple vulnerabilities in third-party dependencies across the frontend (Next.js, PostCSS) and backend (python-multipart, python-dotenv, paramiko, pytest).

---

### Highlights

#### Dependency Security Updates (Frontend)

- **Next.js** updated from `16.1.6` to `16.2.6`
  - Fixes SSRF vulnerability in applications using WebSocket upgrades (High)
  - Fixes Middleware / Proxy bypass via dynamic route parameter injection (High)
  - Fixes Denial of Service via connection exhaustion with Cache Components (High)
  - Fixes Middleware / Proxy bypass in Pages Router applications using i18n (High)
  - Fixes Middleware / Proxy bypass in App Router via segment-prefetch routes (High, including incomplete fix follow-up)
  - Fixes Denial of Service with Server Components (High)
  - Fixes cross-site scripting in `beforeInteractive` scripts with untrusted input (Moderate)
  - Fixes Denial of Service in the Image Optimization API (Moderate)
  - Fixes cache poisoning in React Server Component responses (Moderate)
  - Fixes cross-site scripting in App Router applications using CSP nonces (Moderate)
  - Fixes cache poisoning via collisions in React Server Component cache-busting (Low)
  - Fixes Middleware / Proxy redirect cache poisoning (Low)

- **PostCSS** forced to `8.5.15` via npm `overrides`
  - Fixes XSS via unescaped `</style>` in CSS Stringify output (Moderate)

#### Dependency Security Updates (Backend)

- **python-multipart** updated from `0.0.22` to `0.0.29`
  - Fixes Denial of Service via unbounded multipart part headers (High)
  - Fixes Denial of Service via large multipart preamble or epilogue data (Moderate)

- **python-dotenv** updated from `1.0.1` to `1.2.2`
  - Fixes symlink following in `set_key` allowing arbitrary file overwrite via cross-device rename fallback (Moderate)

- **paramiko** updated from `3.5.0` to `5.0.0`
  - Fixes `rsakey.py` allowing the SHA-1 algorithm (Low)

- **pytest** updated from `8.3.4` to `9.0.3`
  - Fixes vulnerable tmpdir handling (Moderate)

- **pytest-asyncio** updated from `0.25.2` to `1.3.0`
  - Required to maintain compatibility with pytest 9.x

---

### Upgrade Notes

- No database migration required for this release.
- No configuration changes required.
- After pulling, run `npm install` in `upservx/` and `pip install -r requirements.txt` in `upservx-service/` to apply updated dependencies.
