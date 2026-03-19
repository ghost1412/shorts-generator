import os
import hashlib
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

def decrypt_secret(encrypted_text: str) -> str:
    """
    Decrypts a secret that was encrypted using the Node.js crypto utility.
    Format: iv_hex : encrypted_hex
    """
    if not encrypted_text or ':' not in encrypted_text:
        return encrypted_text
        
    try:
        # Get master key from environment and hash to exactly 32 bytes
        master_key = os.getenv('ENCRYPTION_KEY', 'shortsflow-placeholder-master-key-32chars')
        key = hashlib.sha256(master_key.encode()).digest()

        # Split IV and ciphertext
        parts = encrypted_text.split(':')
        iv = bytes.fromhex(parts[0])
        ciphertext = bytes.fromhex(parts[1])

        # Decrypt using AES-256-CBC
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()

        # Remove PKCS7 padding
        padding_len = padded_data[-1]
        return padded_data[:-padding_len].decode('utf-8')
    except Exception as e:
        print(f"Error decrypting secret: {e}")
        return encrypted_text
