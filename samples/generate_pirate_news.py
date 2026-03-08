#!/usr/bin/env python3
"""Generate a **signed** OPA archive that asks an AI agent to summarise
headline news in pirate-speak and pick the article most relevant to AI
enthusiasts.

The archive bundles:
  - A prompt (prompt.md)
  - The Google News RSS feed (data/headlines.xml)
  - A JAR-style digital signature (META-INF/SIGNATURE.{SF,RSA})

Usage:
    python generate_pirate_news.py          # creates pirate_news.opa
"""

import os
import sys
import subprocess
import textwrap

# Ensure the library is importable from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from opa import (
    OpaArchive,
    Manifest,
    Prompt,
    DataIndex,
    ExecutionMode,
    Signer,
    generate_signing_key,
    generate_self_signed_cert,
)

FEED_URL = "https://news.google.com/rss"
FEED_FILE = os.path.join(os.path.dirname(__file__), "headlines.xml")

PROMPT_TEXT = textwrap.dedent("""\
    # Pirate News Briefing

    You are a salty pirate news anchor.  Your job:

    1. Read the RSS/XML news feed located at `data/headlines.xml`.
    2. Summarise **every headline** in one or two sentences, written entirely
       in over-the-top pirate dialect (plenty of "Arrr!", "Avast!", "shiver
       me timbers", nautical metaphors, etc.).
    3. After the full summary, choose the **single article** that would be of
       most interest to someone passionate about **Artificial Intelligence**
       and write a longer (3-5 sentence) pirate-style commentary on why it
       matters for AI.

    ## Output format

    Produce a **single, self-contained HTML file** (no external assets).
    Use the structure below.  Feel free to add inline CSS to make it look
    like a weathered treasure map or pirate gazette.

    ```html
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Pirate News Briefing</title>
      <style>
        /* your pirate-themed styles here */
      </style>
    </head>
    <body>
      <h1>⚓ Pirate News Briefing ⚓</h1>

      <section id="headlines">
        <h2>Today's Headlines from the Seven Seas</h2>
        <!-- one <article> per headline -->
      </section>

      <section id="ai-pick">
        <h2>🏴‍☠️ The AI Buccaneer's Pick 🏴‍☠️</h2>
        <!-- your AI-focused deep-dive here -->
      </section>
    </body>
    </html>
    ```

    Return **only** the HTML — no markdown fences, no preamble.
""")


def download_feed() -> None:
    """Download the RSS feed if it doesn't already exist (or is empty)."""
    if os.path.isfile(FEED_FILE) and os.path.getsize(FEED_FILE) > 0:
        return
    print(f"Downloading RSS feed from {FEED_URL} ...")
    subprocess.check_call(
        ["curl", "-sL", FEED_URL, "-o", FEED_FILE],
    )
    print(f"  saved to {FEED_FILE} ({os.path.getsize(FEED_FILE)} bytes)")


def main() -> None:
    download_feed()

    manifest = Manifest(
        title="Pirate News Briefing",
        description=(
            "Summarise headline news in pirate dialect and pick the top AI story. "
            "Output a self-contained HTML file."
        ),
        execution_mode=ExecutionMode.BATCH,
    )

    prompt = Prompt(PROMPT_TEXT)

    data_index = DataIndex()
    data_index.add(
        "data/headlines.xml",
        description="Google News headline RSS feed (XML)",
        content_type="application/rss+xml",
    )

    archive = OpaArchive(manifest=manifest, prompt=prompt)
    archive.set_data_index(data_index)
    archive.add_data_file("data/headlines.xml", FEED_FILE)

    out_path = os.path.join(os.path.dirname(__file__), "pirate_news.opa")
    archive.write(out_path)
    print(f"Created {out_path}")

    # --- Sign the archive ---
    print("Generating RSA signing key and self-signed certificate ...")
    private_key = generate_signing_key(key_type="rsa", key_size=2048)
    certificate = generate_self_signed_cert(
        private_key, common_name="Pirate News Signer"
    )

    signer = Signer(private_key=private_key, certificate=certificate)
    signer.sign(out_path)
    print("Archive signed successfully.")

    # Quick sanity check
    import zipfile
    with zipfile.ZipFile(out_path) as zf:
        print("Archive contents:")
        for name in zf.namelist():
            info = zf.getinfo(name)
            print(f"  {name:40s}  {info.file_size:>8,} bytes")


if __name__ == "__main__":
    main()
