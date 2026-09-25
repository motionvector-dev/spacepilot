# Security Policy

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub
issues.**

Report by email to **dev@motionvector.io** with "SECURITY" in the subject
line. Include:

- the affected version (from `spacepilot --version` or the wheel's
  `METADATA`)
- the component (CLI, HTTP `/v1`, FastMCP, dashboard, registry loader)
- reproduction steps or a proof of concept
- what you believe the impact is, if you know

You will get an acknowledgment within **72 hours**. If a fix requires a
release, we will publish it before any public disclosure, and you will be
credited (or kept anonymous, your choice).

## What counts as in scope

- Anything in `spacepilot/` Python code, `spacepilot/web/` static assets,
  `native/SpaceBar/` Swift sources, or `landing/` build output.
- The Python packaging path (`pyproject.toml`, `requirements*.txt`) — a
  dependency that ships something it should not is a security issue.
- The model registry loader (`spacepilot/model_registry.py`), which parses
  YAML from disk — anything that can make it execute or exfiltrate is in
  scope.

## What is NOT in scope

- **Local-only attacks against the dashboard.** SpacePilot's FastAPI
  app is loopback-only by design (`LocalOnlyMiddleware`); attacks that
  require the victim to already be on the same machine, or to have
  voluntarily installed a malicious local package with access to the
  same user's environment, are out of scope for CVE treatment. Those
  should go through the normal issue tracker instead.
- **Self-hosted inference boxes** you manually `spacepilot launch` and SSH
  into yourself. Those are your own machines under your own credentials.
- **The spot-clip / LTX / Hunyuan DiT engine routes.** They exist as
  stubs and every path refuses with 501 — there is no inference path to
  attack there in the current release.
- **Social-engineering Saurabh** via email; be verifying, not phishing.

## If you have already found a remote-code-execution or data-exfiltration
vector

Do not sit on it. Do not demo it on a live machine. Email us immediately
with the exact steps so we can reproduce; we will not take an aggressive
stance on disclosure timing if you acted in good faith.

## Known-hardening rules in this repo

For context, the codebase's own security posture (what is and isn't
trusted):

- **No Doppler / no secret file committed.** `.env.example` is the shape of
  what a deployment wants; real secrets come from `doppler run --` or env
  vars only. Anything user-controlled is passed through `X-SpacePilot-Token`.
- **Every compute-spending endpoint requires `X-SpacePilot-Token`** via
  `require_token`. Read-only and telemetry routes stay open.
  `test_compute_endpoints_all_require_the_token` walks the app and will fail
  on any newly-registered mutating route that skips the dependency.
- **`subprocess` calls are argv lists only.** `run_cmd` rejects strings
  outright; `shell=True` is never reintroduced.
- **Filesystem paths from a request go through `resolve_output`**, which
  resolves and checks containment in `OUTPUTS_DIR`.
- **`innerHTML` on server data goes through `esc()`**; there is a regression
  test that fails if server data is interpolated raw.
- **Wheel import gating**: `tests/test_wheel_install.py` asserts no module
  in the shipped wheel imports a dependency that is not declared in
  `pyproject.toml`.

## Thanks

Thanks for spending time on this. A correct security report is worth more
to us than any feature PR.
