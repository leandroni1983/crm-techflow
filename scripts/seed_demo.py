#!/usr/bin/env python3
"""Carga órdenes de ejemplo en un servidor de DESARROLLO (para ver el tablero con datos). No lo uses en producción.

    OPEN_BROWSER=0 ADMIN_PASSWORD=Secreta123 python -m crm &      # servidor local con SQLite
    python scripts/seed_demo.py http://localhost:8000 admin Secreta123
"""
import http.cookiejar, json, random, sys, urllib.request
from datetime import date, datetime, timedelta, timezone

base, user, pw = sys.argv[1:4] if len(sys.argv) > 3 else ("http://localhost:8000", "admin", "Secreta123")
jar = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(path, data):
    r = op.open(urllib.request.Request(base + path, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"}))
    return json.loads(r.read())


call("/api/login", {"usuario": user, "password": pw})
rnd = random.Random(7)
ESTADOS = ["Recibido", "En diagnóstico", "Presupuesto", "Esperando repuesto", "En reparación", "Listo para retirar", "Entregado"]
EQUIPOS = [("Notebook", "Lenovo"), ("Notebook", "HP"), ("PC de escritorio", "Armada"), ("Celular", "Samsung"), ("Impresora", "Epson"), ("Cortadora de pelo", "Gama"), ("Secador", "Philips"), ("Monitor", "LG")]
FALLAS = ["No enciende", "Pantalla rota", "Muy lenta, necesita limpieza", "No carga la batería", "Se apaga solo por temperatura", "No imprime", "Hace ruido en el ventilador", "Sin imagen"]
NOMBRES = ["Leandro Pérez", "Marta Gómez", "Julián Ríos", "Carla Benítez", "Sergio Molina", "Paula Ferreyra", "Diego Acosta", "Lucía Romero", "Hernán Vega", "Natalia Suárez", "Pablo Ortiz", "Valeria Paz"]
hoy = datetime.now(timezone.utc)
CATALOGO = ["No enciende", "Pantalla rota", "Muy lenta", "Se apaga sola", "No carga o no toma el cargador", "Se calienta o hace ruido el ventilador", "No imprime", "Sin imagen", "Batería agotada", "Virus o malware"]
TELS = {n: f"11{40000000 + i * 1713}" for i, n in enumerate(NOMBRES)}                       # cada cliente tiene su teléfono...
EQ_DE = {n: rnd.sample(EQUIPOS, 2) for n in NOMBRES}                                         # ...y dos equipos que va trayendo
for i in range(60):
    dias = int(rnd.random() ** 1.6 * 175)                      # más órdenes recientes que viejas
    creada = hoy - timedelta(days=dias, hours=rnd.randint(0, 8))
    est = "Entregado" if dias > 3 and rnd.random() < (.35 if dias < 25 else .93) else rnd.choice(ESTADOS if dias < 25 else ESTADOS[:6])
    nombre = rnd.choice(NOMBRES); eq, marca = rnd.choice(EQ_DE[nombre]); monto = rnd.choice([0, 18000, 25000, 38000, 45000, 62000, 95000, 120000]) if est != "Recibido" else 0
    o = {"id": f"demo{i}", "creada": creada.strftime("%Y-%m-%dT%H:%M:%SZ"), "cliente": nombre, "tel": TELS[nombre],
         "equipo": eq, "marca": marca, "serie": f"SN{NOMBRES.index(nombre)}{EQUIPOS.index((eq, marca))}", "fallas": rnd.sample(CATALOGO, rnd.choice([1, 1, 2])),
         "problema": rnd.choice(["", "", "Dice que pasó de un día para el otro", "Lo trajo con el cargador", "Ya lo había llevado a otro lado"]), "estado": est, "monto": str(monto) if monto else "",
         "tecnico": rnd.choice(["admin", "admin", "tecnico1"]), "hora": "10:30", "checklist": rnd.sample(["Enciende", "Con cargador", "Con batería"], 2),
         "diagnostico": "Limpieza interna y cambio de pasta térmica." if monto else "", "historial": [{"t": "Orden creada", "n": True}]}
    if monto:
        o["sena"] = str(rnd.choice([0, 0, 10000, monto // 2])); o["repuestos"] = [{"desc": "Repuesto", "costo": str(int(monto * rnd.choice([.2, .3, .4])))}]
    if est == "Entregado":
        ent = creada + timedelta(days=rnd.randint(1, 9)); o["entrega_fecha"] = min(ent, hoy).strftime("%Y-%m-%d"); o["pagado"] = "1" if rnd.random() < .85 else ""
    if est == "Presupuesto" and dias > 9: o["estado_fecha"] = (hoy - timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if rnd.random() < .12 and est not in ("Entregado", "Listo para retirar"): o["entrega_est"] = (date.today() - timedelta(days=rnd.randint(1, 6))).isoformat()
    call("/api/orden", o)
print("Listo: 60 órdenes de ejemplo cargadas en", base)
