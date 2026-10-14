"""Contraseñas (PBKDF2), hash de tokens de sesión y bloqueo de intentos fallidos de login."""
import hashlib, hmac, secrets, threading, time


def hash_pw(p, salt=None, it=200_000):
    salt = salt or secrets.token_hex(16)
    return f"pbkdf2${it}${salt}${hashlib.pbkdf2_hmac('sha256', p.encode(), bytes.fromhex(salt), it).hex()}"


def check_pw(p, stored):
    try:
        _, it, salt, h = stored.split("$")
        return hmac.compare_digest(hash_pw(p, salt, int(it)).split("$")[3], h)
    except Exception:
        return False


def token_hash(token): return hashlib.sha256(token.encode()).hexdigest()


class LoginLimiter:
    """Bloquea una IP durante `lock_secs` después de `max_fails` intentos fallidos seguidos."""

    def __init__(self, max_fails=5, lock_secs=300):
        self.max_fails, self.lock_secs, self._d, self._lock = max_fails, lock_secs, {}, threading.Lock()

    def blocked(self, ip):
        with self._lock: return self._d.get(ip, [0, 0])[1] > time.time()

    def fail(self, ip):
        with self._lock:
            n = self._d.get(ip, [0, 0])[0] + 1
            self._d[ip] = [0, time.time() + self.lock_secs] if n >= self.max_fails else [n, 0]

    def ok(self, ip):
        with self._lock: self._d.pop(ip, None)
