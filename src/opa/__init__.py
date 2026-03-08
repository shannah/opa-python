"""OPA (Open Prompt Archive) - Python library for generating .opa files."""

from opa.manifest import Manifest, ExecutionMode
from opa.prompt import Prompt
from opa.session import SessionHistory, Message, ContentBlock
from opa.data_assets import DataIndex, DataEntry
from opa.archive import OpaArchive
from opa.signing import (
    Signer,
    generate_signing_key,
    generate_self_signed_cert,
    load_private_key,
    load_certificate,
)

__version__ = "0.1.0"
__all__ = [
    "Manifest",
    "ExecutionMode",
    "Prompt",
    "SessionHistory",
    "Message",
    "ContentBlock",
    "DataIndex",
    "DataEntry",
    "OpaArchive",
    "Signer",
    "generate_signing_key",
    "generate_self_signed_cert",
    "load_private_key",
    "load_certificate",
]
