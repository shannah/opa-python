"""JAR-style digital signing for OPA archives.

Implements the signing convention from the OPA spec:
  - META-INF/SIGNATURE.SF  — SHA-256 digests of the manifest
  - META-INF/SIGNATURE.RSA — PKCS#7 (CMS) detached signature of the .SF

Requires the ``cryptography`` package (optional dependency).
"""

import base64
import hashlib
import re
import zipfile
from typing import Optional, Tuple

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa, padding
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
    )
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives.asymmetric.types import (
        CertificateIssuerPrivateKeyTypes,
    )
    import datetime

    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


def _require_crypto() -> None:
    if not _HAS_CRYPTO:
        raise ImportError(
            "The 'cryptography' package is required for signing. "
            "Install it with: pip install cryptography"
        )


# ---------------------------------------------------------------------------
# Key / certificate generation helpers
# ---------------------------------------------------------------------------

def generate_signing_key(
    *,
    key_type: str = "rsa",
    key_size: int = 2048,
) -> "CertificateIssuerPrivateKeyTypes":
    """Generate a private key for signing (RSA or EC)."""
    _require_crypto()
    if key_type == "rsa":
        return rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    if key_type == "ec":
        return ec.generate_private_key(ec.SECP256R1())
    raise ValueError(f"Unsupported key type: {key_type!r}")


def generate_self_signed_cert(
    private_key: "CertificateIssuerPrivateKeyTypes",
    *,
    common_name: str = "OPA Archive Signer",
    days_valid: int = 365,
) -> "x509.Certificate":
    """Generate a self-signed X.509 certificate for the given key."""
    _require_crypto()
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=days_valid))
        .sign(private_key, hashes.SHA256())
    )
    return cert


def load_private_key(path: str, password: Optional[bytes] = None):
    """Load a PEM-encoded private key from disk."""
    _require_crypto()
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=password)


def load_certificate(path: str) -> "x509.Certificate":
    """Load a PEM-encoded X.509 certificate from disk."""
    _require_crypto()
    with open(path, "rb") as f:
        return x509.load_pem_x509_certificate(f.read())


# ---------------------------------------------------------------------------
# Signature-file (.SF) generation
# ---------------------------------------------------------------------------

def _digest_b64(data: bytes) -> str:
    """Return the base64-encoded SHA-256 digest of *data*."""
    return base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")


def _split_manifest_sections(manifest_bytes: bytes) -> list[bytes]:
    """Split a MANIFEST.MF into its individual sections (as raw bytes).

    The JAR spec defines sections separated by blank lines (\\r\\n\\r\\n).
    For a single-section manifest the whole content is one section.
    """
    text = manifest_bytes
    # Split on double CRLF (section separator).  Keep the trailing CRLF
    # on each section so the digest matches the original bytes exactly.
    parts = re.split(b"\r\n\r\n", text)
    sections = []
    for p in parts:
        p = p.strip(b"\r\n")
        if p:
            sections.append(p + b"\r\n")
    return sections


def build_signature_file(manifest_bytes: bytes) -> bytes:
    """Build the SIGNATURE.SF content from a serialised MANIFEST.MF."""
    lines: list[str] = []
    lines.append("Signature-Version: 1.0")
    lines.append(f"SHA-256-Digest-Manifest: {_digest_b64(manifest_bytes)}")
    lines.append(f"Created-By: opa-archive (Python)")

    # Per-section digests
    sections = _split_manifest_sections(manifest_bytes)
    for section in sections:
        lines.append("")
        lines.append(f"SHA-256-Digest: {_digest_b64(section)}")

    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


# ---------------------------------------------------------------------------
# PKCS#7 / CMS signature block
# ---------------------------------------------------------------------------

def _sign_sf_rsa(sf_bytes: bytes, private_key, cert) -> bytes:
    """Create a DER-encoded PKCS#7 signature block for the .SF content."""
    from cryptography.hazmat.primitives.serialization import pkcs7

    # Build a PKCS#7 signed-data structure (detached signature)
    builder = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(sf_bytes)
        .add_signer(cert, private_key, hashes.SHA256())
    )
    return builder.sign(Encoding.DER, [pkcs7.PKCS7Options.Binary])


def _block_file_extension(private_key) -> str:
    """Return the META-INF block file extension for the key type."""
    if isinstance(private_key, rsa.RSAPrivateKey):
        return "RSA"
    if isinstance(private_key, ec.EllipticCurvePrivateKey):
        return "EC"
    return "RSA"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class Signer:
    """Signs an OPA archive using JAR signing conventions.

    Usage::

        signer = Signer(private_key=key, certificate=cert)
        archive.write("task.opa")
        signer.sign("task.opa")            # modifies ZIP in-place
        # — or —
        signer.sign_bytes(archive_bytes)    # returns signed bytes
    """

    def __init__(self, *, private_key, certificate: "x509.Certificate"):
        _require_crypto()
        self._key = private_key
        self._cert = certificate
        self._ext = _block_file_extension(private_key)

    def sign(self, path: str) -> None:
        """Add signature entries to an existing .opa file in-place."""
        # Read all existing entries
        entries: list[Tuple[str, bytes]] = []
        manifest_bytes: Optional[bytes] = None

        with zipfile.ZipFile(path, "r") as zf:
            for name in zf.namelist():
                data = zf.read(name)
                entries.append((name, data))
                if name == "META-INF/MANIFEST.MF":
                    manifest_bytes = data

        if manifest_bytes is None:
            raise ValueError("Archive has no META-INF/MANIFEST.MF")

        sf_bytes = build_signature_file(manifest_bytes)
        block_bytes = _sign_sf_rsa(sf_bytes, self._key, self._cert)

        # Re-write the ZIP with signature entries added
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in entries:
                zf.writestr(name, data)
            zf.writestr("META-INF/SIGNATURE.SF", sf_bytes)
            zf.writestr(f"META-INF/SIGNATURE.{self._ext}", block_bytes)

    def sign_bytes(self, archive_bytes: bytes) -> bytes:
        """Sign an in-memory archive and return the signed bytes."""
        import io

        entries: list[Tuple[str, bytes]] = []
        manifest_bytes: Optional[bytes] = None

        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as zf:
            for name in zf.namelist():
                data = zf.read(name)
                entries.append((name, data))
                if name == "META-INF/MANIFEST.MF":
                    manifest_bytes = data

        if manifest_bytes is None:
            raise ValueError("Archive has no META-INF/MANIFEST.MF")

        sf_bytes = build_signature_file(manifest_bytes)
        block_bytes = _sign_sf_rsa(sf_bytes, self._key, self._cert)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in entries:
                zf.writestr(name, data)
            zf.writestr("META-INF/SIGNATURE.SF", sf_bytes)
            zf.writestr(f"META-INF/SIGNATURE.{self._ext}", block_bytes)
        return buf.getvalue()
