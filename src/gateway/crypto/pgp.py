"""
PGP (Pretty Good Privacy) encryption and signing for unitMail.

This module provides PGP encryption, decryption, signing, and
verification capabilities using the python-gnupg library.
"""

import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Union

try:
    import gnupg
except ImportError:
    gnupg = None  # type: ignore

from src.common.exceptions import CryptoError, DecryptionError, EncryptionError, SignatureError

logger = logging.getLogger(__name__)


class KeyType(Enum):
    """Types of PGP keys."""

    RSA = "RSA"
    DSA = "DSA"
    ECDSA = "ECDSA"
    EDDSA = "EDDSA"
    ELGAMAL = "ELG"


class TrustLevel(Enum):
    """PGP key trust levels."""

    UNKNOWN = "unknown"
    UNDEFINED = "undefined"
    NEVER = "never"
    MARGINAL = "marginal"
    FULL = "full"
    ULTIMATE = "ultimate"


@dataclass
class PGPKey:
    """Information about a PGP key."""

    fingerprint: str
    keyid: str
    type: str
    length: int
    uids: list[str] = field(default_factory=list)
    creation_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    trust: str = "unknown"
    is_expired: bool = False
    is_revoked: bool = False
    can_encrypt: bool = True
    can_sign: bool = True
    subkeys: list[str] = field(default_factory=list)

    @property
    def primary_uid(self) -> str:
        """Get the primary user ID."""
        return self.uids[0] if self.uids else ""

    @property
    def email(self) -> Optional[str]:
        """Extract email from primary UID."""
        uid = self.primary_uid
        if "<" in uid and ">" in uid:
            return uid[uid.index("<") + 1:uid.index(">")]
        return None


@dataclass
class EncryptionResult:
    """Result of an encryption operation."""

    success: bool
    data: str
    status: str
    armored: bool = True


@dataclass
class DecryptionResult:
    """Result of a decryption operation."""

    success: bool
    data: str
    status: str
    fingerprint: Optional[str] = None
    key_id: Optional[str] = None
    signature_valid: Optional[bool] = None
    signature_fingerprint: Optional[str] = None


@dataclass
class SignatureResult:
    """Result of a signing operation."""

    success: bool
    data: str
    status: str
    fingerprint: Optional[str] = None
    key_id: Optional[str] = None


@dataclass
class VerificationResult:
    """Result of a signature verification."""

    valid: bool
    fingerprint: Optional[str] = None
    key_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    username: Optional[str] = None
    status: str = ""
    trust_level: str = "unknown"


class PGPManager:
    """
    Manager for PGP operations using GnuPG.

    Provides key management, encryption, decryption, signing,
    and verification capabilities.
    """

    def __init__(
        self,
        gnupg_home: Optional[str] = None,
        gpg_binary: str = "gpg",
        use_agent: bool = True,
        keyring: Optional[str] = None,
    ) -> None:
        """
        Initialize the PGP manager.

        Args:
            gnupg_home: Path to GnuPG home directory.
            gpg_binary: Path to GPG binary.
            use_agent: Whether to use GPG agent.
            keyring: Path to custom keyring.

        Raises:
            CryptoError: If gnupg library is not available.
        """
        if gnupg is None:
            raise CryptoError(
                "python-gnupg library is required for PGP operations. "
                "Install it with: pip install python-gnupg"
            )

        # Set up GnuPG home directory
        if gnupg_home:
            self.gnupg_home = gnupg_home
            os.makedirs(gnupg_home, exist_ok=True)
        else:
            self.gnupg_home = os.path.expanduser("~/.gnupg")

        # Initialize GPG
        options = []
        if not use_agent:
            options.append("--no-use-agent")
        if keyring:
            options.extend(["--keyring", keyring])

        try:
            self._gpg = gnupg.GPG(
                gnupghome=self.gnupg_home,
                gpgbinary=gpg_binary,
                options=options,
            )
            self._gpg.encoding = "utf-8"
        except Exception as e:
            raise CryptoError(f"Failed to initialize GnuPG: {e}")

        logger.info(
            "Initialized PGP manager with home=%s",
            self.gnupg_home,
        )

    def generate_key(
        self,
        name: str,
        email: str,
        passphrase: Optional[str] = None,
        key_type: str = "RSA",
        key_length: int = 4096,
        expire_date: Optional[str] = None,
        comment: str = "",
    ) -> PGPKey:
        """
        Generate a new PGP key pair.

        Args:
            name: User's real name.
            email: User's email address.
            passphrase: Passphrase for the private key.
            key_type: Key algorithm (RSA, DSA, etc.).
            key_length: Key size in bits.
            expire_date: Expiration date (e.g., "1y", "365", "0" for never).
            comment: Optional comment for the key.

        Returns:
            PGPKey object with generated key information.

        Raises:
            CryptoError: If key generation fails.
        """
        try:
            # Build key input
            key_input = self._gpg.gen_key_input(
                key_type=key_type,
                key_length=key_length,
                name_real=name,
                name_email=email,
                name_comment=comment,
                passphrase=passphrase,
                expire_date=expire_date or "0",
            )

            # Generate key
            key = self._gpg.gen_key(key_input)

            if not key.fingerprint:
                raise CryptoError(f"Key generation failed: {key.status}")

            logger.info(
                "Generated PGP key for %s <%s>, fingerprint=%s",
                name,
                email,
                key.fingerprint,
            )

            return self.get_key(key.fingerprint)

        except CryptoError:
            raise
        except Exception as e:
            raise CryptoError(f"Failed to generate PGP key: {e}")

    def list_keys(self, secret: bool = False) -> list[PGPKey]:
        """
        List keys in the keyring.

        Args:
            secret: If True, list secret (private) keys only.

        Returns:
            List of PGPKey objects.
        """
        try:
            keys = self._gpg.list_keys(secret=secret)
            result = []

            for key_data in keys:
                key = self._parse_key_data(key_data)
                result.append(key)

            return result

        except Exception as e:
            logger.error("Failed to list keys: %s", str(e))
            return []

    def get_key(self, key_id: str, secret: bool = False) -> Optional[PGPKey]:
        """
        Get a specific key by fingerprint or key ID.

        Args:
            key_id: Key fingerprint or ID.
            secret: If True, look for secret key.

        Returns:
            PGPKey object or None if not found.
        """
        try:
            keys = self._gpg.list_keys(secret=secret, keys=[key_id])

            if not keys:
                return None

            return self._parse_key_data(keys[0])

        except Exception as e:
            logger.error("Failed to get key %s: %s", key_id, str(e))
            return None

    def _parse_key_data(self, key_data: dict) -> PGPKey:
        """Parse key data from GnuPG into PGPKey object."""
        # Parse dates
        creation_date = None
        if key_data.get("date"):
            try:
                creation_date = datetime.fromtimestamp(int(key_data["date"]))
            except (ValueError, TypeError):
                pass

        expiration_date = None
        if key_data.get("expires"):
            try:
                expiration_date = datetime.fromtimestamp(
                    int(key_data["expires"]))
            except (ValueError, TypeError):
                pass

        # Check capabilities
        caps = key_data.get("cap", "")

        return PGPKey(
            fingerprint=key_data.get("fingerprint", ""),
            keyid=key_data.get("keyid", ""),
            type=key_data.get("type", ""),
            length=int(key_data.get("length", 0)),
            uids=key_data.get("uids", []),
            creation_date=creation_date,
            expiration_date=expiration_date,
            trust=key_data.get("trust", "unknown"),
            is_expired=key_data.get("expires", "") == "expired",
            is_revoked=key_data.get("trust", "") == "r",
            can_encrypt="e" in caps or "E" in caps,
            can_sign="s" in caps or "S" in caps,
            subkeys=[sk[0] for sk in key_data.get("subkeys", [])],
        )

    def delete_key(
        self,
        key_id: str,
        secret: bool = False,
        passphrase: Optional[str] = None,
    ) -> bool:
        """
        Delete a key from the keyring.

        Args:
            key_id: Key fingerprint or ID.
            secret: If True, delete secret key.
            passphrase: Passphrase for secret key deletion.

        Returns:
            True if deletion was successful.
        """
        try:
            if secret:
                result = self._gpg.delete_keys(
                    key_id,
                    secret=True,
                    passphrase=passphrase,
                )
            else:
                result = self._gpg.delete_keys(key_id)

            success = result.status == "ok"

            if success:
                logger.info("Deleted key %s", key_id)
            else:
                logger.warning("Failed to delete key %s: %s",
                               key_id, result.status)

            return success

        except Exception as e:
            logger.error("Failed to delete key %s: %s", key_id, str(e))
            return False

    def export_key(
        self,
        key_id: str,
        secret: bool = False,
        armor: bool = True,
        passphrase: Optional[str] = None,
    ) -> str:
        """
        Export a key from the keyring.

        Args:
            key_id: Key fingerprint or ID.
            secret: If True, export secret key.
            armor: If True, export in ASCII armor format.
            passphrase: Passphrase for secret key export.

        Returns:
            Exported key data.

        Raises:
            CryptoError: If export fails.
        """
        try:
            if secret:
                result = self._gpg.export_keys(
                    key_id,
                    secret=True,
                    armor=armor,
                    passphrase=passphrase,
                )
            else:
                result = self._gpg.export_keys(key_id, armor=armor)

            if not result:
                raise CryptoError(f"Failed to export key {key_id}")

            return result

        except CryptoError:
            raise
        except Exception as e:
            raise CryptoError(f"Failed to export key {key_id}: {e}")

    def import_key(self, key_data: str) -> list[PGPKey]:
        """
        Import a key into the keyring.

        Args:
            key_data: ASCII-armored or binary key data.

        Returns:
            List of imported PGPKey objects.

        Raises:
            CryptoError: If import fails.
        """
        try:
            result = self._gpg.import_keys(key_data)

            if not result.fingerprints:
                raise CryptoError(
                    f"Failed to import key: {
                        result.results[0].get(
                            'text', 'Unknown error')}"
                    if result.results
                    else "Failed to import key: No keys found"
                )

            imported_keys = []
            for fingerprint in result.fingerprints:
                if fingerprint:
                    key = self.get_key(fingerprint)
                    if key:
                        imported_keys.append(key)

            logger.info(
                "Imported %d key(s): %s",
                len(imported_keys),
                ", ".join(k.fingerprint for k in imported_keys),
            )

            return imported_keys

        except CryptoError:
            raise
        except Exception as e:
            raise CryptoError(f"Failed to import key: {e}")

    def import_key_from_file(self, filepath: str) -> list[PGPKey]:
        """
        Import a key from a file.

        Args:
            filepath: Path to the key file.

        Returns:
            List of imported PGPKey objects.
        """
        try:
            with open(filepath, "r") as f:
                key_data = f.read()
            return self.import_key(key_data)
        except CryptoError:
            raise
        except Exception as e:
            raise CryptoError(f"Failed to import key from {filepath}: {e}")

    def search_keyserver(
        self,
        query: str,
        keyserver: str = "keys.openpgp.org",
    ) -> list[dict]:
        """
        Search for keys on a keyserver.

        Args:
            query: Search query (email, name, or key ID).
            keyserver: Keyserver address.

        Returns:
            List of matching key information dictionaries.
        """
        try:
            result = self._gpg.search_keys(query, keyserver)
            return list(result)

        except Exception as e:
            logger.error(
                "Keyserver search failed for %s: %s",
                query,
                str(e),
            )
            return []

    def fetch_key_from_keyserver(
        self,
        key_id: str,
        keyserver: str = "keys.openpgp.org",
    ) -> Optional[PGPKey]:
        """
        Fetch and import a key from a keyserver.

        Args:
            key_id: Key ID or fingerprint to fetch.
            keyserver: Keyserver address.

        Returns:
            Imported PGPKey or None if not found.
        """
        try:
            result = self._gpg.recv_keys(keyserver, key_id)

            if result.fingerprints:
                fingerprint = result.fingerprints[0]
                logger.info(
                    "Fetched key %s from %s",
                    fingerprint,
                    keyserver,
                )
                return self.get_key(fingerprint)

            logger.warning(
                "Key %s not found on %s",
                key_id,
                keyserver,
            )
            return None

        except Exception as e:
            logger.error(
                "Failed to fetch key %s from %s: %s",
                key_id,
                keyserver,
                str(e),
            )
            return None

    def upload_key_to_keyserver(
        self,
        key_id: str,
        keyserver: str = "keys.openpgp.org",
    ) -> bool:
        """
        Upload a public key to a keyserver.

        Args:
            key_id: Key ID or fingerprint to upload.
            keyserver: Keyserver address.

        Returns:
            True if upload was successful.
        """
        try:
            result = self._gpg.send_keys(keyserver, key_id)
            success = result.ok

            if success:
                logger.info(
                    "Uploaded key %s to %s",
                    key_id,
                    keyserver,
                )
            else:
                logger.warning(
                    "Failed to upload key %s to %s: %s",
                    key_id,
                    keyserver,
                    result.status,
                )

            return success

        except Exception as e:
            logger.error(
                "Failed to upload key %s to %s: %s",
                key_id,
                keyserver,
                str(e),
            )
            return False

    def encrypt(
        self,
        data: Union[str, bytes],
        recipients: list[str],
        sign: bool = False,
        sign_key: Optional[str] = None,
        passphrase: Optional[str] = None,
        armor: bool = True,
        always_trust: bool = False,
    ) -> EncryptionResult:
        """
        Encrypt data for one or more recipients.

        Args:
            data: Data to encrypt.
            recipients: List of recipient key IDs or emails.
            sign: Whether to sign the encrypted data.
            sign_key: Key to use for signing.
            passphrase: Passphrase for signing key.
            armor: Whether to ASCII-armor the output.
            always_trust: Trust all keys regardless of trust level.

        Returns:
            EncryptionResult with encrypted data.

        Raises:
            EncryptionError: If encryption fails.
        """
        try:
            if isinstance(data, str):
                data = data.encode("utf-8")

            encrypted = self._gpg.encrypt(
                data,
                recipients,
                sign=sign_key if sign else None,
                passphrase=passphrase,
                armor=armor,
                always_trust=always_trust,
            )

            if not encrypted.ok:
                raise EncryptionError(
                    f"Encryption failed: {encrypted.status}"
                )

            logger.debug(
                "Encrypted data for %d recipient(s)",
                len(recipients),
            )

            return EncryptionResult(
                success=True,
                data=str(encrypted),
                status=encrypted.status,
                armored=armor,
            )

        except EncryptionError:
            raise
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")

    def decrypt(
        self,
        data: Union[str, bytes],
        passphrase: Optional[str] = None,
        always_trust: bool = False,
    ) -> DecryptionResult:
        """
        Decrypt PGP-encrypted data.

        Args:
            data: Encrypted data to decrypt.
            passphrase: Passphrase for the decryption key.
            always_trust: Trust all keys regardless of trust level.

        Returns:
            DecryptionResult with decrypted data.

        Raises:
            DecryptionError: If decryption fails.
        """
        try:
            if isinstance(data, str):
                data = data.encode("utf-8")

            decrypted = self._gpg.decrypt(
                data,
                passphrase=passphrase,
                always_trust=always_trust,
            )

            if not decrypted.ok:
                raise DecryptionError(
                    f"Decryption failed: {decrypted.status}"
                )

            # Check for signature
            signature_valid = None
            signature_fingerprint = None
            if decrypted.fingerprint:
                signature_valid = decrypted.valid
                signature_fingerprint = decrypted.fingerprint

            logger.debug("Decrypted data successfully")

            return DecryptionResult(
                success=True,
                data=str(decrypted),
                status=decrypted.status,
                fingerprint=decrypted.fingerprint,
                key_id=decrypted.key_id,
                signature_valid=signature_valid,
                signature_fingerprint=signature_fingerprint,
            )

        except DecryptionError:
            raise
        except Exception as e:
            raise DecryptionError(f"Decryption failed: {e}")

    def sign(
        self,
        data: Union[str, bytes],
        key_id: Optional[str] = None,
        passphrase: Optional[str] = None,
        detach: bool = False,
        clearsign: bool = False,
        armor: bool = True,
    ) -> SignatureResult:
        """
        Sign data with a PGP key.

        Args:
            data: Data to sign.
            key_id: Key to use for signing (default key if None).
            passphrase: Passphrase for the signing key.
            detach: Create a detached signature.
            clearsign: Create a clearsigned message.
            armor: ASCII-armor the signature.

        Returns:
            SignatureResult with signed data or signature.

        Raises:
            SignatureError: If signing fails.
        """
        try:
            if isinstance(data, str):
                data = data.encode("utf-8")

            signed = self._gpg.sign(
                data,
                keyid=key_id,
                passphrase=passphrase,
                detach=detach,
                clearsign=clearsign,
                armor=armor,
            )

            if not signed.data:
                raise SignatureError(f"Signing failed: {signed.status}")

            logger.debug(
                "Signed data with key %s",
                key_id or "default",
            )

            return SignatureResult(
                success=True,
                data=str(signed),
                status=signed.status,
                fingerprint=signed.fingerprint,
                key_id=signed.key_id,
            )

        except SignatureError:
            raise
        except Exception as e:
            raise SignatureError(f"Signing failed: {e}")

    def verify(
        self,
        data: Union[str, bytes],
        signature: Optional[Union[str, bytes]] = None,
    ) -> VerificationResult:
        """
        Verify a PGP signature.

        Args:
            data: Signed data or data to verify.
            signature: Detached signature (if applicable).

        Returns:
            VerificationResult with verification status.
        """
        try:
            if isinstance(data, str):
                data = data.encode("utf-8")

            if signature:
                # Verify detached signature
                if isinstance(signature, str):
                    signature = signature.encode("utf-8")

                # Write data to temp file for verification
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(data)
                    tmp_path = tmp.name

                try:
                    verified = self._gpg.verify_data(tmp_path, signature)
                finally:
                    os.unlink(tmp_path)
            else:
                # Verify inline signature
                verified = self._gpg.verify(data)

            # Parse timestamp
            timestamp = None
            if verified.timestamp:
                try:
                    timestamp = datetime.fromtimestamp(
                        float(verified.timestamp))
                except (ValueError, TypeError):
                    pass

            result = VerificationResult(
                valid=verified.valid,
                fingerprint=verified.fingerprint,
                key_id=verified.key_id,
                timestamp=timestamp,
                username=verified.username,
                status=verified.status,
                trust_level=verified.trust_level if hasattr(
                    verified, 'trust_level') else "unknown",
            )

            if result.valid:
                logger.debug(
                    "Signature verified, key=%s",
                    verified.fingerprint,
                )
            else:
                logger.warning(
                    "Signature verification failed: %s",
                    verified.status,
                )

            return result

        except Exception as e:
            logger.error("Signature verification error: %s", str(e))
            return VerificationResult(
                valid=False,
                status=f"Verification error: {e}",
            )

    def encrypt_file(
        self,
        input_path: str,
        output_path: str,
        recipients: list[str],
        sign: bool = False,
        sign_key: Optional[str] = None,
        passphrase: Optional[str] = None,
        armor: bool = True,
    ) -> bool:
        """
        Encrypt a file for one or more recipients.

        Args:
            input_path: Path to file to encrypt.
            output_path: Path for encrypted output.
            recipients: List of recipient key IDs.
            sign: Whether to sign the encrypted data.
            sign_key: Key to use for signing.
            passphrase: Passphrase for signing key.
            armor: ASCII-armor the output.

        Returns:
            True if encryption was successful.
        """
        try:
            with open(input_path, "rb") as f:
                encrypted = self._gpg.encrypt_file(
                    f,
                    recipients,
                    sign=sign_key if sign else None,
                    passphrase=passphrase,
                    armor=armor,
                    output=output_path,
                )

            return encrypted.ok

        except Exception as e:
            logger.error("File encryption failed: %s", str(e))
            return False

    def decrypt_file(
        self,
        input_path: str,
        output_path: str,
        passphrase: Optional[str] = None,
    ) -> bool:
        """
        Decrypt a PGP-encrypted file.

        Args:
            input_path: Path to encrypted file.
            output_path: Path for decrypted output.
            passphrase: Passphrase for decryption key.

        Returns:
            True if decryption was successful.
        """
        try:
            with open(input_path, "rb") as f:
                decrypted = self._gpg.decrypt_file(
                    f,
                    passphrase=passphrase,
                    output=output_path,
                )

            return decrypted.ok

        except Exception as e:
            logger.error("File decryption failed: %s", str(e))
            return False

    def set_key_trust(
        self,
        key_id: str,
        trust_level: TrustLevel,
    ) -> bool:
        """
        Set the trust level for a key.

        Args:
            key_id: Key fingerprint or ID.
            trust_level: Trust level to set.

        Returns:
            True if trust was set successfully.
        """
        trust_values = {
            TrustLevel.UNKNOWN: "1",
            TrustLevel.UNDEFINED: "2",
            TrustLevel.NEVER: "3",
            TrustLevel.MARGINAL: "4",
            TrustLevel.FULL: "5",
            TrustLevel.ULTIMATE: "6",
        }

        try:
            result = self._gpg.trust_keys(
                key_id,
                trust_values[trust_level],
            )
            return result.ok if hasattr(result, 'ok') else True

        except Exception as e:
            logger.error(
                "Failed to set trust for key %s: %s",
                key_id,
                str(e),
            )
            return False


def create_pgp_manager(
    gnupg_home: Optional[str] = None,
) -> PGPManager:
    """
    Create a PGP manager with default settings.

    Args:
        gnupg_home: Path to GnuPG home directory.

    Returns:
        Configured PGPManager instance.
    """
    return PGPManager(gnupg_home=gnupg_home)
