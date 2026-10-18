"""QR y PDF. La lectura del QR necesita OpenCV (opcional): sin él, esa prueba se omite."""
import os, shutil, tempfile, unittest

from crm.media import MediaStore
from crm.pdf import pdf_comprobante
from crm.qr import qr_matrix
from tests.helpers import jpeg_url


class QrTest(unittest.TestCase):
    def test_se_puede_leer(self):
        try: import cv2, numpy as np
        except ImportError: self.skipTest("sin OpenCV")
        det = cv2.QRCodeDetector()
        for t in ("0001071026", "OT-0012071026", "x" * 40, "Taller ñandú 0005"):
            rows = qr_matrix(t); n = len(rows); img = np.full((n + 8, n + 8), 255, np.uint8)
            for y, r in enumerate(rows):
                for x, c in enumerate(r):
                    if c == "1": img[y + 4, x + 4] = 0
            val, _, _ = det.detectAndDecode(cv2.resize(img, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST))
            self.assertEqual(val, t)

    def test_texto_demasiado_largo(self):
        with self.assertRaises(ValueError): qr_matrix("x" * 500)


class PdfTest(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp, True); self.m = MediaStore(self.tmp)

    def test_estructura_y_tamano_a5(self):
        filas = [["Cliente", "Juan Ñandú (con paréntesis)"], ["Falla informada", "No enciende " * 8, True]]
        pdf = pdf_comprobante({"numero": "0001", "taller": "Taller Pérez", "filas": filas, "condiciones": "Condiciones " * 30}, self.m)
        self.assertTrue(pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"/MediaBox [0 0 595.28 419.53]", pdf)                         # A5 apaisado por defecto
        a4 = pdf_comprobante({"numero": "1", "ancho_mm": "297", "alto_mm": "210", "filas": []}, self.m)
        self.assertIn(b"/MediaBox [0 0 841.89 595.28]", a4)

    def test_fotos_y_firma_desde_archivos_o_dataurl(self):
        url = self.m.save("o1", jpeg_url())
        pdf = pdf_comprobante({"numero": "1", "filas": [], "firma": url, "fotos": [url, jpeg_url(), "/media/o1/noexiste.jpg", "basura"]}, self.m)
        self.assertEqual(pdf.count(b"/Subtype /Image"), 3)                            # firma + 2 fotos válidas; lo inválido se ignora
        self.assertEqual(pdf.count(b"/Type /Page "), 2)                               # la hoja principal + la de fotos


if __name__ == "__main__": unittest.main()
