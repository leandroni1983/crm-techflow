"""Seguridad básica y línea de comandos (en un proceso aparte, como en Docker)."""
import os, shutil, subprocess, sys, tempfile, unittest

from crm.security import LoginLimiter, check_pw, hash_pw, token_hash

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SecurityTest(unittest.TestCase):
    def test_hash_y_verificacion(self):
        h = hash_pw("MiClave123"); self.assertTrue(h.startswith("pbkdf2$200000$"))
        self.assertTrue(check_pw("MiClave123", h)); self.assertFalse(check_pw("otra", h)); self.assertFalse(check_pw("x", "basura"))
        self.assertNotEqual(hash_pw("MiClave123"), h)                                  # cada hash lleva su sal
        self.assertEqual(len(token_hash("t")), 64)

    def test_limitador(self):
        l = LoginLimiter(max_fails=3, lock_secs=60)
        for _ in range(2): l.fail("1.1.1.1")
        self.assertFalse(l.blocked("1.1.1.1")); l.fail("1.1.1.1"); self.assertTrue(l.blocked("1.1.1.1")); self.assertFalse(l.blocked("2.2.2.2"))
        l.ok("1.1.1.1"); self.assertFalse(l.blocked("1.1.1.1"))


class CliTest(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_cli(self, *args, **env):
        e = {**os.environ, "DATA_DIR": self.tmp, "PYTHONPATH": ROOT}; e.pop("DATABASE_URL", None); e.update(env)
        return subprocess.run([sys.executable, "-m", "crm", *args], env=e, capture_output=True, text=True, cwd=ROOT)

    def test_check_db_reset_y_list(self):
        r = self.run_cli("check-db"); self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("Motor: SQLite", r.stdout)
        self.assertIn("Escritura de prueba: ok (deshecha)", r.stdout); self.assertIn("ATENCIÓN", r.stdout)  # avisa que no es PostgreSQL
        self.assertIn("Listo", self.run_cli("reset-password", "admin", "NuevaClave123").stdout)
        self.assertIn("admin  (admin)", self.run_cli("list-users").stdout)
        self.assertIn("al menos 8", self.run_cli("reset-password", "admin", "corta").stdout)

    def test_exigir_postgres_evita_caer_en_sqlite(self):
        r = self.run_cli("check-db", REQUIRE_POSTGRES="1"); self.assertEqual(r.returncode, 1); self.assertIn("exige PostgreSQL", r.stdout)
        r = self.run_cli("serve", REQUIRE_POSTGRES="1", DATABASE_URL="sqlite:///" + os.path.join(self.tmp, "x.db")); self.assertEqual(r.returncode, 1)

    def test_version(self):
        self.assertRegex(self.run_cli("version").stdout.strip(), r"^\d+\.\d+\.\d+$")


if __name__ == "__main__": unittest.main()
