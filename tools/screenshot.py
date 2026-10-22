#!/usr/bin/env python3
"""Optional render check: build the sample site, serve it, and take headless-Chrome screenshots,
reporting any browser console errors. Needs Playwright (pip install playwright) and Chrome/Chromium.

  python3 tools/screenshot.py [--chrome /usr/bin/google-chrome] [--out preview]
Exits non-zero if any page has console errors or the leaderboard table doesn't render."""
import argparse, functools, http.server, json, os, sys, tempfile, threading
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))
import build  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--chrome", default=None, help="Chrome executable (default: Playwright's bundled Chromium)")
ap.add_argument("--out", default=os.path.join(REPO, "preview"))
ap.add_argument("--site", help="serve this already-built folder instead of building the sample")
a = ap.parse_args()
site = a.site or tempfile.mkdtemp(prefix="sbffc-site-")
if not a.site:
    build.main(["--out", site, "--sample"])
os.makedirs(a.out, exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
handler = functools.partial(Quiet, directory=site)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"
shots = [("desktop_index", "/index.html#view=championship", (1366, 900)),
         ("desktop_leaderboard_html", "/leaderboard.html#view=divisions", (1366, 900)),
         ("mobile_index", "/index.html#view=championship", (390, 844)),
         ("squarespace_snippet_test", "/snippet-test.html", (1366, 900))]
report, bad = {}, False
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=a.chrome, args=["--no-sandbox"]) if a.chrome else p.chromium.launch()
    for name, path, vp in shots:
        mobile = vp[0] < 500
        ctx = b.new_context(viewport={"width": vp[0], "height": vp[1]}, device_scale_factor=2 if mobile else 1,
                            is_mobile=mobile, has_touch=mobile)
        pg = ctx.new_page(); errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("requestfailed", lambda r: errs.append(f"request failed: {r.url}"))
        pg.goto(base + path, wait_until="networkidle")
        ok = True
        try:
            pg.wait_for_selector(".lb-view table, .lb-view .lb-grid", timeout=10000)
        except Exception:
            ok = False
        pg.wait_for_timeout(500)
        f = os.path.join(a.out, name + ".png"); pg.screenshot(path=f)
        rows = pg.evaluate("() => document.querySelectorAll('.lb-view tbody tr').length")
        report[name] = {"screenshot": f, "rendered": ok, "table_rows": rows, "console_errors": errs}
        bad |= (not ok) or bool(errs)
        ctx.close()
    b.close()
srv.shutdown()
print(json.dumps(report, indent=1))
sys.exit(1 if bad else 0)
