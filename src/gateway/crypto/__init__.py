"""
Cryptography modules for unitMail Gateway.

This package provides cryptographic functionality for email security:
- DKIM signing and verification
- TLS configuration and certificate management
- PGP encryption, decryption, signing, and verification
"""

from .dkim import (
    DKIMKeyPair,
    DKIMSignature,
    DKIMSigner,
    DKIMVerifier,
    generate_dkim_keys,
)
from .pgp import (
    DecryptionResult,
    EncryptionResult,
    KeyType,
    PGPKey,
    PGPManager,
    SignatureResult,
    TrustLevel,
    VerificationResult,
    create_pgp_manager,
)
from .tls import (
    CertificateInfo,
    CertificateManager,
    CertificateType,
    LetsEncryptHelper,
    TLS_1_2_CIPHERS,
    TLS_1_3_CIPHERS,
    TLSConfig,
    TLSContextFactory,
    TLSVersion,
    create_default_tls_config,
)

__all__ = [
    # DKIM
    "DKIMKeyPair",
    "DKIMSignature",
    "DKIMSigner",
    "DKIMVerifier",
    "generate_dkim_keys",
    # TLS
    "CertificateInfo",
    "CertificateManager",
    "CertificateType",
    "LetsEncryptHelper",
    "TLS_1_2_CIPHERS",
    "TLS_1_3_CIPHERS",
    "TLSConfig",
    "TLSContextFactory",
    "TLSVersion",
    "create_default_tls_config",
    # PGP
    "DecryptionResult",
    "EncryptionResult",
    "KeyType",
    "PGPKey",
    "PGPManager",
    "SignatureResult",
    "TrustLevel",
    "VerificationResult",
    "create_pgp_manager",
]
