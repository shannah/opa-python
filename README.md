# opa-archive

A Python library for creating and signing [OPA (Open Prompt Archive)](https://github.com/nicholasgasior/opa) files.

OPA is a ZIP-based archive format for packaging AI prompts together with data assets, session history, and metadata -- similar to how JAR files package Java applications.

## Installation

```bash
pip install opa-archive
```

## Quick Start

```python
from opa import OpaArchive, Manifest, Prompt, ExecutionMode

manifest = Manifest(
    title="My Prompt",
    description="A packaged AI prompt with data",
    execution_mode=ExecutionMode.BATCH,
)

prompt = Prompt("Summarise the attached data file.")

archive = OpaArchive(manifest=manifest, prompt=prompt)
archive.add_data_file("data/report.csv", "local/report.csv")
archive.write("my_prompt.opa")
```

## Features

- **Manifest** -- JAR-style `MANIFEST.MF` with title, description, execution mode, and custom fields.
- **Prompt** -- Markdown prompt files with `{{variable}}` template support.
- **Data assets** -- Bundle arbitrary files and directories with a typed `INDEX.json` catalog.
- **Session history** -- Include multi-turn conversation context (text, images, tool use).
- **Signing** -- JAR-compatible PKCS#7 digital signatures using the `cryptography` library or the `openssl` CLI.

## Signing an Archive

```python
from opa import OpaArchive, Manifest, Prompt, Signer
from opa import generate_signing_key, generate_self_signed_cert

# Build the archive
archive = OpaArchive(
    manifest=Manifest(title="Signed Example"),
    prompt=Prompt("Hello, world!"),
)
archive.write("example.opa")

# Generate a key pair and sign
private_key = generate_signing_key(key_type="rsa", key_size=2048)
certificate = generate_self_signed_cert(private_key, common_name="My Signer")

signer = Signer(private_key=private_key, certificate=certificate)
signer.sign("example.opa")
```

You can also load existing PEM keys:

```python
from opa import load_private_key, load_certificate, Signer

key = load_private_key("key.pem")
cert = load_certificate("cert.pem")
signer = Signer(private_key=key, certificate=cert)
signer.sign("example.opa")
```

## Template Variables

Prompts support `{{variable}}` placeholders:

```python
prompt = Prompt("Translate the following to {{language}}:\n\n{{text}}")
print(prompt.variables())  # {'language', 'text'}
print(prompt.render({"language": "French", "text": "Hello"}))
```

## Data Assets

Bundle files with a typed index:

```python
from opa import DataIndex

index = DataIndex()
index.add("data/feed.xml", description="RSS feed", content_type="application/rss+xml")
index.add("data/config.json", description="Config file", content_type="application/json")

archive.set_data_index(index)
archive.add_data_file("data/feed.xml", "local/feed.xml")
archive.add_data_dir("local/data_folder/", archive_prefix="data/")
```

## Session History

Include conversation context:

```python
from opa import SessionHistory

session = SessionHistory()
session.add_user("What is the capital of France?")
session.add_assistant("The capital of France is Paris.")

archive.set_session(session)
```

## Dependencies

The core library has **no required dependencies**. Signing works out of the box if `openssl` is on your PATH. Install the optional `cryptography` package for native Python signing:

```bash
pip install opa-archive[crypto]
```

## License

MIT
