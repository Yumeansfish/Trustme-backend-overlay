#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a tiny GitHub Pages release index from release metadata.")
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--release-tag", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata_path = Path(args.metadata).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    asset_name = payload["asset_name"]
    download_url = (
        f"https://github.com/{args.repository}/releases/download/"
        f"{args.release_tag}/{asset_name}"
    )

    index_html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Trust-me Browser-Line Release</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f5efe4;
        --panel: #fffaf2;
        --ink: #1f1d18;
        --muted: #5d594f;
        --accent: #0d6b4d;
      }}
      body {{
        margin: 0;
        font-family: "Iowan Old Style", "Palatino Linotype", serif;
        background: radial-gradient(circle at top, #fffaf0, var(--bg));
        color: var(--ink);
      }}
      main {{
        max-width: 760px;
        margin: 4rem auto;
        padding: 2rem;
      }}
      .card {{
        background: var(--panel);
        border: 1px solid #ded4c3;
        border-radius: 18px;
        padding: 2rem;
        box-shadow: 0 18px 40px rgba(31, 29, 24, 0.08);
      }}
      h1 {{
        margin-top: 0;
        font-size: 2rem;
      }}
      dl {{
        display: grid;
        grid-template-columns: max-content 1fr;
        gap: 0.75rem 1rem;
        margin: 1.5rem 0;
      }}
      dt {{
        color: var(--muted);
      }}
      a.button {{
        display: inline-block;
        margin-top: 1rem;
        padding: 0.9rem 1.2rem;
        border-radius: 999px;
        background: var(--accent);
        color: white;
        text-decoration: none;
      }}
      code {{
        font-family: "SFMono-Regular", Menlo, monospace;
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="card">
        <h1>Trust-me Browser-Line Release</h1>
        <p>Portable browser-line bundle assembled from upstream ActivityWatch modules plus the Trust-me backend overlay.</p>
        <dl>
          <dt>Version</dt><dd><code>{html.escape(payload["version"])}</code></dd>
          <dt>Platform</dt><dd><code>{html.escape(payload["platform"])}</code></dd>
          <dt>Arch</dt><dd><code>{html.escape(payload["arch"])}</code></dd>
          <dt>Backend Overlay</dt><dd><code>{html.escape(payload["backend_overlay_rev"])}</code></dd>
          <dt>Frontend</dt><dd><code>{html.escape(payload["frontend_rev"])}</code></dd>
          <dt>Upstream</dt><dd><code>{html.escape(payload["upstream_rev"])}</code></dd>
          <dt>Built At</dt><dd><code>{html.escape(payload["built_at_utc"])}</code></dd>
        </dl>
        <a class="button" href="{html.escape(download_url)}">Download Bundle</a>
      </section>
    </main>
  </body>
</html>
"""

    (output_dir / "index.html").write_text(index_html, encoding="utf-8")
    (output_dir / "release.json").write_text(
        json.dumps({**payload, "download_url": download_url}, indent=2, sort_keys=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
