"""Tests for OPA archive signing."""

import io
import zipfile

from opa.archive import OpaArchive
from opa.manifest import Manifest
from opa.prompt import Prompt
from opa.signing import (
    Signer,
    build_signature_file,
    generate_signing_key,
    generate_self_signed_cert,
)


def _make_archive() -> OpaArchive:
    return OpaArchive(
        manifest=Manifest(title="Sign Test"),
        prompt=Prompt("Test prompt."),
    )


def _make_signer():
    key = generate_signing_key(key_type="rsa", key_size=2048)
    cert = generate_self_signed_cert(key, common_name="Test Signer")
    return Signer(private_key=key, certificate=cert)


def test_build_signature_file():
    manifest_bytes = b"Manifest-Version: 1.0\r\nOPA-Version: 0.1\r\n"
    sf = build_signature_file(manifest_bytes)
    text = sf.decode("utf-8")
    assert "Signature-Version: 1.0" in text
    assert "SHA-256-Digest-Manifest:" in text
    assert "SHA-256-Digest:" in text


def test_sign_bytes():
    archive = _make_archive()
    raw = archive.to_bytes()
    signer = _make_signer()
    signed = signer.sign_bytes(raw)

    with zipfile.ZipFile(io.BytesIO(signed)) as zf:
        names = zf.namelist()
        assert "META-INF/SIGNATURE.SF" in names
        assert "META-INF/SIGNATURE.RSA" in names
        # Original entries still present
        assert "META-INF/MANIFEST.MF" in names
        assert "prompt.md" in names

        # SF content is well-formed
        sf = zf.read("META-INF/SIGNATURE.SF").decode("utf-8")
        assert "Signature-Version: 1.0" in sf

        # RSA block is non-empty DER
        rsa_block = zf.read("META-INF/SIGNATURE.RSA")
        assert len(rsa_block) > 100


def test_sign_file(tmp_path):
    archive = _make_archive()
    path = str(tmp_path / "test.opa")
    archive.write(path)

    signer = _make_signer()
    signer.sign(path)

    with zipfile.ZipFile(path) as zf:
        assert "META-INF/SIGNATURE.SF" in zf.namelist()
        assert "META-INF/SIGNATURE.RSA" in zf.namelist()


def test_ec_key_signing():
    key = generate_signing_key(key_type="ec")
    cert = generate_self_signed_cert(key, common_name="EC Signer")
    signer = Signer(private_key=key, certificate=cert)

    archive = _make_archive()
    signed = signer.sign_bytes(archive.to_bytes())

    with zipfile.ZipFile(io.BytesIO(signed)) as zf:
        assert "META-INF/SIGNATURE.EC" in zf.namelist()


def test_no_manifest_raises():
    """Signing an archive without a manifest should raise."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("empty.txt", b"no manifest here")

    signer = _make_signer()
    try:
        signer.sign_bytes(buf.getvalue())
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "MANIFEST" in str(e)
