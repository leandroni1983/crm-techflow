"""Coherencia de la parte web sin abrir un navegador: archivos referenciados y elementos que el JavaScript busca."""
import glob, json, os, re, unittest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crm", "web")
read = lambda *p: open(os.path.join(WEB, *p), encoding="utf-8").read()
DINAMICOS = {"bImp", "pgsize"}  # se crean desde el propio JavaScript


class WebTest(unittest.TestCase):
    def test_las_plantillas_solo_referencian_archivos_que_existen(self):
        for tpl in glob.glob(os.path.join(WEB, "templates", "*.html")):
            for ref in re.findall(r'(?:src|href)="(/static/[^"]+)"', open(tpl, encoding="utf-8").read()):
                self.assertTrue(os.path.isfile(os.path.join(WEB, ref.lstrip("/"))), f"{os.path.basename(tpl)} -> {ref}")

    def test_el_manifest_y_el_service_worker_apuntan_a_archivos_reales(self):
        m = json.loads(read("manifest.webmanifest"))
        for icon in m["icons"]: self.assertTrue(os.path.isfile(os.path.join(WEB, icon["src"].lstrip("/"))), icon["src"])
        for ref in re.findall(r"'(/static/[^']+)'", read("sw.js")): self.assertTrue(os.path.isfile(os.path.join(WEB, ref.lstrip("/"))), ref)
        nombres = re.search(r"\[((?:'\w+',?\s*)+)\]\.map", read("sw.js"))
        for n in re.findall(r"'(\w+)'", nombres.group(1)): self.assertTrue(os.path.isfile(os.path.join(WEB, "static", "js", n + ".js")), n)

    def test_el_service_worker_guarda_todos_los_scripts_de_la_pagina(self):
        # si falta uno, la app instalada no abre sin conexión
        usados = set(re.findall(r'src="/static/js/(\w+)\.js"', read("templates", "index.html")))
        sw = set(re.findall(r"'(\w+)'", re.search(r"\[((?:'\w+',?\s*)+)\]\.map", read("sw.js")).group(1)))
        self.assertEqual(usados, sw)

    def test_todos_los_scripts_de_la_pagina_estan_listados_como_protegidos(self):
        from crm.api.handler import PROTECTED_STATIC
        usados = set(re.findall(r'src="/static/(js/\w+\.js)"', read("templates", "index.html")))
        self.assertEqual(usados, PROTECTED_STATIC)  # si agregás un script, también tiene que pedir sesión

    def test_cada_id_que_busca_el_javascript_existe_en_la_pagina(self):
        html = read("templates", "index.html"); ids = set(re.findall(r'id="([\w-]+)"', html))
        faltan = []
        for f in sorted(glob.glob(os.path.join(WEB, "static", "js", "*.js"))):
            if f.endswith("login.js"): continue
            for i in set(re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", open(f, encoding="utf-8").read())):
                if i not in ids and i not in DINAMICOS: faltan.append(f"{os.path.basename(f)}: #{i}")
        self.assertEqual(faltan, [])

    def test_login_js_usa_ids_de_login_html(self):
        ids = set(re.findall(r'id="([\w-]+)"', read("templates", "login.html")))
        for i in set(re.findall(r"\$\('([\w-]+)'\)", read("static", "js", "login.js"))): self.assertIn(i, ids)

    def test_los_iconos_del_sprite_existen(self):
        html = read("templates", "index.html"); simbolos = set(re.findall(r'<symbol id="(i-[\w-]+)"', html))
        usados = set(re.findall(r'#(i-[\w-]+)', html)) | {"i-" + n for f in glob.glob(os.path.join(WEB, "static", "js", "*.js"))
                                                         for n in re.findall(r"ic\('([\w-]+)'", open(f, encoding="utf-8").read())}
        usados |= {m for f in glob.glob(os.path.join(WEB, "static", "js", "*.js")) for m in re.findall(r'#(i-[\w-]+)', open(f, encoding="utf-8").read())}
        self.assertEqual(sorted(usados - simbolos), [])


if __name__ == "__main__": unittest.main()
