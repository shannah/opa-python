"""JAR-style digital signing for OPA archives.

Implements the signing convention from the OPA spec:
  - META-INF/SIGNATURE.SF  — SHA-256 digests of the manifest
  - META-INF/SIGNATURE.RSA — PKCS#7 (CMS) detached signature of the .SF

Uses the ``openssl`` CLI (available on macOS and most Linux systems) by
default.  Falls back to the ``cryptography`` Python package when available.
No pip-installed dependencies are required if ``openssl`` is on the PATH.
"""

import base64
import hashlib
import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Optional: try to import the ``cryptography`` package
# ---------------------------------------------------------------------------

try:
    from cryptography import x509 as _crypto_x509
    from cryptography.hazmat.primitives import hashes as _crypto_hashes
    from cryptography.hazmat.primitives import serialization as _crypto_serial
    from cryptography.hazmat.primitives.asymmetric import (
        ec as _crypto_ec,
        rsa as _crypto_rsa,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding as _Encoding,
        NoEncryption as _NoEncryption,
        PrivateFormat as _PrivateFormat,
    )
    from cryptography.x509.oid import NameOID as _NameOID
    import datetime as _dt

    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


def _has_openssl() -> bool:
    return shutil.which("openssl") is not None


# ---------------------------------------------------------------------------
# PEM bundle (used by the openssl-CLI backend)
# ---------------------------------------------------------------------------

class _PemBundle:
    """Holds PEM-encoded private key + certificate bytes."""

    def __init__(self, key_pem: bytes, cert_pem: bytes, key_type: str = "rsa"):
        self.key_pem = key_pem
        self.cert_pem = cert_pem
        self.key_type = key_type


# ---------------------------------------------------------------------------
# Key / certificate generation
# ---------------------------------------------------------------------------

def generate_signing_key(
    *,
    key_type: str = "rsa",
    key_size: int = 2048,
):
    """Generate a private key for signing.

    Returns a ``cryptography`` key object when that package is installed,
    otherwise returns a ``_PemBundle`` generated via the ``openssl`` CLI.
    The return value is accepted by ``generate_self_signed_cert`` and
    ``Signer`` regardless of backend.
    """
    if _HAS_CRYPTO:
        if key_type == "rsa":
            return _crypto_rsa.generate_private_key(
                public_exponent=65537, key_size=key_size,
            )
        if key_type == "ec":
            return _crypto_ec.generate_private_key(_crypto_ec.SECP256R1())
        raise ValueError(f"Unsupported key type: {key_type!r}")

    if not _has_openssl():
        raise RuntimeError(
            "Neither the 'cryptography' Python package nor the 'openssl' "
            "CLI could be found.  Install one of them to enable signing."
        )
    if key_type == "rsa":
        key_pem = subprocess.check_output(
            ["openssl", "genrsa", str(key_size)],
            stderr=subprocess.DEVNULL,
        )
    elif key_type == "ec":
        key_pem = subprocess.check_output(
            ["openssl", "ecparam", "-genkey", "-name", "prime256v1", "-noout"],
            stderr=subprocess.DEVNULL,
        )
    else:
        raise ValueError(f"Unsupported key type: {key_type!r}")
    return _PemBundle(key_pem, b"", key_type=key_type)


def generate_self_signed_cert(
    private_key,
    *,
    common_name: str = "OPA Archive Signer",
    days_valid: int = 365,
):
    """Generate a self-signed X.509 certificate.

    *private_key* is either a ``cryptography`` key object or a
    ``_PemBundle`` from ``generate_signing_key``.
    Returns the same type enriched with the certificate.
    """
    if isinstance(private_key, _PemBundle):
        return _openssl_self_signed_cert(
            private_key, common_name=common_name, days_valid=days_valid,
        )

    if not _HAS_CRYPTO:
        raise ImportError(
            "The 'cryptography' package is required when passing "
            "cryptography key objects."
        )
    subject = issuer = _crypto_x509.Name([
        _crypto_x509.NameAttribute(_NameOID.COMMON_NAME, common_name),
    ])
    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (
        _crypto_x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(_crypto_x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + _dt.timedelta(days=days_valid))
        .sign(private_key, _crypto_hashes.SHA256())
    )
    return cert


def _openssl_self_signed_cert(
    bundle: "_PemBundle",
    *,
    common_name: str,
    days_valid: int,
) -> "_PemBundle":
    """Use ``openssl req`` to create a self-signed certificate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = os.path.join(tmpdir, "key.pem")
        cert_path = os.path.join(tmpdir, "cert.pem")
        with open(key_path, "wb") as f:
            f.write(bundle.key_pem)

        subprocess.check_call(
            [
                "openssl", "req", "-new", "-x509",
                "-key", key_path,
                "-out", cert_path,
                "-days", str(days_valid),
                "-subj", f"/CN={common_name}",
                "-sha256",
            ],
            stderr=subprocess.DEVNULL,
        )
        with open(cert_path, "rb") as f:
            cert_pem = f.read()

    return _PemBundle(bundle.key_pem, cert_pem, key_type=bundle.key_type)


def load_private_key(path: str, password: Optional[bytes] = None):
    """Load a PEM-encoded private key from disk."""
    with open(path, "rb") as f:
        pem_data = f.read()
    if _HAS_CRYPTO:
        return _crypto_serial.load_pem_private_key(pem_data, password=password)
    key_type = "ec" if b"EC PRIVATE KEY" in pem_data else "rsa"
    return _PemBundle(pem_data, b"", key_type=key_type)


def load_certificate(path: str):
    """Load a PEM-encoded X.509 certificate from disk."""
    with open(path, "rb") as f:
        pem_data = f.read()
    if _HAS_CRYPTO:
        return _crypto_x509.load_pem_x509_certificate(pem_data)
    return pem_data


# ---------------------------------------------------------------------------
# Signature-file (.SF) generation  (pure Python — no dependencies)
# ---------------------------------------------------------------------------

def _digest_b64(data: bytes) -> str:
    """Return the base64-encoded SHA-256 digest of *data*."""
    return base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")


def _split_manifest_sections(manifest_bytes: bytes) -> List[bytes]:
    """Split a MANIFEST.MF into its individual sections (as raw bytes).

    The JAR spec defines sections separated by blank lines (\\r\\n\\r\\n).
    For a single-section manifest the whole content is one section.
    """
    parts = re.split(b"\r\n\r\n", manifest_bytes)
    sections: List[bytes] = []
    for p in parts:
        p = p.strip(b"\r\n")
        if p:
            sections.append(p + b"\r\n")
    return sections


def build_signature_file(manifest_bytes: bytes) -> bytes:
    """Build the SIGNATURE.SF content from a serialised MANIFEST.MF."""
    lines: List[str] = []
    lines.append("Signature-Version: 1.0")
    lines.append(f"SHA-256-Digest-Manifest: {_digest_b64(manifest_bytes)}")
    lines.append("Created-By: opa-archive (Python)")

    for section in _split_manifest_sections(manifest_bytes):
        lines.append("")
        lines.append(f"SHA-256-Digest: {_digest_b64(section)}")

    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


# ---------------------------------------------------------------------------
# PKCS#7 / CMS signature block
# ---------------------------------------------------------------------------

def _sign_sf_crypto(sf_bytes: bytes, private_key, cert) -> bytes:
    """Create a DER-encoded PKCS#7 signature using ``cryptography``."""
    from cryptography.hazmat.primitives.serialization import pkcs7

    builder = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(sf_bytes)
        .add_signer(cert, private_key, _crypto_hashes.SHA256())
    )
    return builder.sign(_Encoding.DER, [pkcs7.PKCS7Options.Binary])


def _sign_sf_openssl(sf_bytes: bytes, bundle: "_PemBundle") -> bytes:
    """Create a DER-encoded CMS signature using the ``openssl`` CLI."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sf_path = os.path.join(tmpdir, "signature.sf")
        key_path = os.path.join(tmpdir, "key.pem")
        cert_path = os.path.join(tmpdir, "cert.pem")
        out_path = os.path.join(tmpdir, "signature.der")

        with open(sf_path, "wb") as f:
            f.write(sf_bytes)
        with open(key_path, "wb") as f:
            f.write(bundle.key_pem)
        with open(cert_path, "wb") as f:
            f.write(bundle.cert_pem)

        subprocess.check_call(
            [
                "openssl", "cms", "-sign",
                "-binary",
                "-in", sf_path,
                "-signer", cert_path,
                "-inkey", key_path,
                "-outform", "DER",
                "-out", out_path,
                "-md", "sha256",
            ],
            stderr=subprocess.DEVNULL,
        )
        with open(out_path, "rb") as f:
            return f.read()


def _block_file_extension(private_key) -> str:
    """Return the META-INF block file extension for the key type."""
    if isinstance(private_key, _PemBundle):
        return "EC" if private_key.key_type == "ec" else "RSA"
    if _HAS_CRYPTO:
        if isinstance(private_key, _crypto_ec.EllipticCurvePrivateKey):
            return "EC"
    return "RSA"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class Signer:
    """Signs an OPA archive using JAR signing conventions.

    Works with either ``cryptography`` key/cert objects or ``_PemBundle``
    objects produced by this module's helper functions (openssl backend).

    Usage::

        key = generate_signing_key()
        cert = generate_self_signed_cert(key, common_name="My Signer")
        signer = Signer(private_key=key, certificate=cert)
        archive.write("task.opa")
        signer.sign("task.opa")
    """

    def __init__(self, *, private_key, certificate):
        self._key = private_key
        self._cert = certificate
        self._ext = _block_file_extension(private_key)
        self._use_openssl = isinstance(private_key, _PemBundle)

    def _make_block(self, sf_bytes: bytes) -> bytes:
        if self._use_openssl:
            return _sign_sf_openssl(sf_bytes, self._key)
        return _sign_sf_crypto(sf_bytes, self._key, self._cert)

    def _inject_signature(
        self, entries: List[Tuple[str, bytes]],
    ) -> List[Tuple[str, bytes]]:
        manifest_bytes: Optional[bytes] = None
        for name, data in entries:
            if name == "META-INF/MANIFEST.MF":
                manifest_bytes = data
                break

        if manifest_bytes is None:
            raise ValueError("Archive has no META-INF/MANIFEST.MF")

        sf_bytes = build_signature_file(manifest_bytes)
        block_bytes = self._make_block(sf_bytes)

        out: List[Tuple[str, bytes]] = list(entries)
        out.append(("META-INF/SIGNATURE.SF", sf_bytes))
        out.append((f"META-INF/SIGNATURE.{self._ext}", block_bytes))
        return out

    def sign(self, path: str) -> None:
        """Add signature entries to an existing .opa file in-place."""
        entries: List[Tuple[str, bytes]] = []
        with zipfile.ZipFile(path, "r") as zf:
            for name in zf.namelist():
                entries.append((name, zf.read(name)))

        signed = self._inject_signature(entries)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in signed:
                zf.writestr(name, data)

    def sign_bytes(self, archive_bytes: bytes) -> bytes:
        """Sign an in-memory archive and return the signed bytes."""
        entries: List[Tuple[str, bytes]] = []
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as zf:
            for name in zf.namelist():
                entries.append((name, zf.read(name)))

        signed = self._inject_signature(entries)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in signed:
                zf.writestr(name, data)
        return buf.getvalue()
