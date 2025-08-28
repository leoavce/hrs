import os, hashlib, binascii

def pbkdf2_hash(password: str, salt: bytes | None = None, rounds: int = 200_000) -> tuple[str,str]:
    if salt is None: salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, rounds, dklen=32)
    return binascii.hexlify(salt).decode(), binascii.hexlify(dk).decode()

def pbkdf2_verify(password: str, salt_hex: str, hash_hex: str, rounds: int = 200_000) -> bool:
    salt = binascii.unhexlify(salt_hex.encode())
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, rounds, dklen=32)
    return binascii.hexlify(dk).decode() == hash_hex
