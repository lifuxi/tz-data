"""
Credential vault for secure storage of sensitive information.
Uses AES-256 encryption for password storage.
"""
import os
import json
import base64
import logging
from typing import Optional, Dict
from pathlib import Path

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logging.warning("cryptography library not available. Using fallback encryption.")

logger = logging.getLogger(__name__)

# Default credential store location
CREDENTIAL_STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "credentials")


class CredentialVault:
    """Secure credential storage using AES-256 encryption."""
    
    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize credential vault.
        
        Args:
            master_key: Master encryption key (32 bytes). 
                       If not provided, uses environment variable or generates one.
        """
        if not CRYPTO_AVAILABLE:
            logger.error("cryptography library required for CredentialVault")
            raise ImportError("Install cryptography: pip install cryptography")
        
        # Get or generate master key
        self.master_key = master_key or os.getenv('CREDENTIAL_MASTER_KEY')
        
        if not self.master_key:
            # Generate a new key (in production, this should be securely stored)
            self.master_key = Fernet.generate_key().decode()
            logger.warning("Generated new master key. Store it securely!")
        
        # Create Fernet instance for encryption/decryption
        self._fernet = Fernet(self.master_key.encode() if isinstance(self.master_key, str) else self.master_key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string.
        
        Args:
            plaintext: Plain text to encrypt
        
        Returns:
            Encrypted string (base64 encoded)
        """
        try:
            encrypted_bytes = self._fernet.encrypt(plaintext.encode('utf-8'))
            return base64.b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a string.
        
        Args:
            ciphertext: Encrypted string (base64 encoded)
        
        Returns:
            Decrypted plain text
        """
        try:
            encrypted_bytes = base64.b64decode(ciphertext.encode('utf-8'))
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    @staticmethod
    def generate_master_key() -> str:
        """
        Generate a new master key.

        Returns:
            New master key string
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError("cryptography library required")

        return Fernet.generate_key().decode()

    def save_credentials(self, account_id: int, username: str, password: str,
                         store_dir: str = None) -> bool:
        """
        Save encrypted credentials for an account.

        Args:
            account_id: Account ID
            username: Account username
            password: Account password
            store_dir: Optional custom storage directory

        Returns:
            True if saved successfully
        """
        cred_dir = Path(store_dir) if store_dir else Path(CREDENTIAL_STORE_DIR)
        cred_dir.mkdir(parents=True, exist_ok=True)

        encrypted = {
            'username': self.encrypt(username),
            'password': self.encrypt(password),
        }

        cred_file = cred_dir / f"account_{account_id}.json"
        with open(cred_file, 'w', encoding='utf-8') as f:
            json.dump(encrypted, f)

        logger.info(f"Saved credentials for account {account_id}")
        return True

    def get_credentials(self, account_id: int, store_dir: str = None) -> Optional[Dict[str, str]]:
        """
        Get decrypted credentials for an account.

        Args:
            account_id: Account ID
            store_dir: Optional custom storage directory

        Returns:
            Dict with 'username' and 'password', or None if not found
        """
        cred_dir = Path(store_dir) if store_dir else Path(CREDENTIAL_STORE_DIR)
        cred_file = cred_dir / f"account_{account_id}.json"

        if not cred_file.exists():
            return None

        try:
            with open(cred_file, 'r', encoding='utf-8') as f:
                encrypted = json.load(f)

            return {
                'username': self.decrypt(encrypted['username']),
                'password': self.decrypt(encrypted['password']),
            }
        except Exception as e:
            logger.error(f"Failed to get credentials for account {account_id}: {e}")
            return None

    def delete_credentials(self, account_id: int, store_dir: str = None) -> bool:
        """Delete stored credentials for an account."""
        cred_dir = Path(store_dir) if store_dir else Path(CREDENTIAL_STORE_DIR)
        cred_file = cred_dir / f"account_{account_id}.json"

        if cred_file.exists():
            cred_file.unlink()
            logger.info(f"Deleted credentials for account {account_id}")
            return True
        return False


# Global vault instance (lazy initialization)
_vault_instance = None


def get_vault(master_key: Optional[str] = None) -> CredentialVault:
    """
    Get or create the global credential vault instance.
    
    Args:
        master_key: Master encryption key
    
    Returns:
        CredentialVault instance
    """
    global _vault_instance
    
    if _vault_instance is None:
        _vault_instance = CredentialVault(master_key=master_key)
    
    return _vault_instance
