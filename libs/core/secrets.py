"""Secrets management abstraction layer.

Provides a unified interface for storing and retrieving sensitive credentials.
Uses GCP Secret Manager in production (when GCP_PROJECT_ID is set) and falls
back to local Fernet symmetric encryption for development.

Usage:
    from libs.core.secrets import SecretManager

    sm = SecretManager()
    secret_id = await sm.store_secret("user-123-binance-key", "my_api_key_value")
    value = await sm.get_secret("user-123-binance-key")
    await sm.delete_secret("user-123-binance-key")
"""

import os
import base64
import json
from typing import Optional

from cryptography.fernet import Fernet

from libs.observability import get_logger

logger = get_logger("secrets-manager")

# Local file-based secret store for development
_LOCAL_SECRETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".dev_secrets")


def _get_fernet() -> Fernet:
    """Get or create a Fernet key for local dev encryption."""
    key_path = os.path.join(_LOCAL_SECRETS_DIR, ".fernet_key")
    os.makedirs(_LOCAL_SECRETS_DIR, exist_ok=True)

    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
        logger.info("Generated new local Fernet encryption key for development")

    return Fernet(key)


class SecretManager:
    """Unified secret storage with GCP Secret Manager + local Fernet fallback."""

    def __init__(self, gcp_project_id: Optional[str] = None):
        """Initialize the secret manager.

        Args:
            gcp_project_id: GCP project ID. If empty/None, uses local Fernet fallback.
        """
        self._gcp_project_id = gcp_project_id or ""
        self._use_gcp = bool(self._gcp_project_id)

        if self._use_gcp:
            try:
                from google.cloud import secretmanager
                self._client = secretmanager.SecretManagerServiceClient()
                logger.info("Using GCP Secret Manager", project=self._gcp_project_id)
            except ImportError:
                logger.warning(
                    "google-cloud-secret-manager not installed, falling back to local Fernet"
                )
                self._use_gcp = False

        if not self._use_gcp:
            self._fernet = _get_fernet()
            logger.info("Using local Fernet encryption (development mode)")

    async def store_secret(self, secret_id: str, plaintext: str) -> str:
        """Store a secret value.

        Args:
            secret_id: Unique identifier for the secret (e.g. 'user-uuid-binance-apikey').
            plaintext: The secret value to encrypt and store.

        Returns:
            The secret_id reference string for database storage.
        """
        if self._use_gcp:
            return self._gcp_store(secret_id, plaintext)
        else:
            return self._local_store(secret_id, plaintext)

    async def get_secret(self, secret_id: str) -> str:
        """Retrieve a secret value.

        Args:
            secret_id: The secret reference ID.

        Returns:
            The decrypted plaintext value.

        Raises:
            FileNotFoundError: If the secret does not exist.
        """
        if self._use_gcp:
            return self._gcp_get(secret_id)
        else:
            return self._local_get(secret_id)

    async def delete_secret(self, secret_id: str) -> None:
        """Permanently destroy a secret.

        Args:
            secret_id: The secret reference ID.
        """
        if self._use_gcp:
            self._gcp_delete(secret_id)
        else:
            self._local_delete(secret_id)

    # ---- GCP Secret Manager Implementation ----

    def _gcp_store(self, secret_id: str, plaintext: str) -> str:
        """Store secret in GCP Secret Manager."""
        from google.cloud import secretmanager
        from google.api_core import exceptions as gcp_exceptions

        parent = f"projects/{self._gcp_project_id}"
        secret_path = f"{parent}/secrets/{secret_id}"

        try:
            self._client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {"replication": {"automatic": {}}},
                }
            )
        except gcp_exceptions.AlreadyExists:
            pass  # Secret already exists, just add a new version

        self._client.add_secret_version(
            request={
                "parent": secret_path,
                "payload": {"data": plaintext.encode("utf-8")},
            }
        )
        logger.info("Stored secret in GCP SM", secret_id=secret_id)
        return secret_id

    def _gcp_get(self, secret_id: str) -> str:
        """Retrieve secret from GCP Secret Manager."""
        name = f"projects/{self._gcp_project_id}/secrets/{secret_id}/versions/latest"
        response = self._client.access_secret_version(request={"name": name})
        return response.payload.data.decode("utf-8")

    def _gcp_delete(self, secret_id: str) -> None:
        """Delete secret from GCP Secret Manager."""
        name = f"projects/{self._gcp_project_id}/secrets/{secret_id}"
        self._client.delete_secret(request={"name": name})
        logger.info("Deleted secret from GCP SM", secret_id=secret_id)

    # ---- Local Fernet Fallback (Development) ----

    def _local_store(self, secret_id: str, plaintext: str) -> str:
        """Store secret locally using Fernet encryption."""
        os.makedirs(_LOCAL_SECRETS_DIR, exist_ok=True)
        encrypted = self._fernet.encrypt(plaintext.encode("utf-8"))
        filepath = os.path.join(_LOCAL_SECRETS_DIR, f"{secret_id}.enc")
        with open(filepath, "wb") as f:
            f.write(encrypted)
        logger.info("Stored secret locally (Fernet)", secret_id=secret_id)
        return secret_id

    def _local_get(self, secret_id: str) -> str:
        """Retrieve locally stored Fernet-encrypted secret."""
        filepath = os.path.join(_LOCAL_SECRETS_DIR, f"{secret_id}.enc")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Secret not found: {secret_id}")
        with open(filepath, "rb") as f:
            encrypted = f.read()
        return self._fernet.decrypt(encrypted).decode("utf-8")

    def _local_delete(self, secret_id: str) -> None:
        """Delete a locally stored secret file."""
        filepath = os.path.join(_LOCAL_SECRETS_DIR, f"{secret_id}.enc")
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info("Deleted local secret", secret_id=secret_id)
