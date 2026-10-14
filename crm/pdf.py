"""Comprobantes en PDF (A5 apaisado configurable) generados a mano, sin dependencias externas."""
import base64, struct
from .qr import qr_matrix


def _esc(t):
    return str(t).encode("cp1252", "replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(s, width, size):
    maxc = max(10, int(width / (size * 0.52)))
    out = []
    for par in str(s or "-").split("\n"):
        line = ""
        for w in par.split():
            while len(w) > maxc:
                if line: out.append(line); line = ""
                out.append(w[:maxc]); w = w[maxc:]
            if len(line) + len(w) + (1 if line else 0) > maxc:
                out.append(line); line = w
            else:
                line = (line + " " + w) if line else w
        out.append(line)
    return out or ["-"]


def _jpeg(src, media):
    """Imagen JPEG -> (bytes, ancho, alto, componentes) o None. `src` es una URL /media/... o un dataURL."""
    try:
        if src.startswith("/media/"):
            b = media.read(src)
            if b is None: return None
        else:
            b = base64.b64decode(src.split(",", 1)[1])
        if b[:2] != b"\xff\xd8": return None
        i = 2
        while i < len(b) - 9:
            if b[i] != 0xFF: i += 1; continue
            m = b[i + 1]
            if m in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", b[i + 5:i + 9]); return b, w, h, b[i + 9]
            if m == 0xFF or m == 0x01 or 0xD0 <= m <= 0xD8: i += 1 if m == 0xFF else 2; continue
            i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    except Exception:
        return None
    return None


def pdf_comprobante(d, media):
    mm = 72 / 25.4
    W = round(float(d.get("ancho_mm") or 210) * mm, 2); H = round(float(d.get("alto_mm") or 148) * mm, 2)
    M = 26; inner = W - 2 * M; cw = inner / 2
    pages, cur, imgs = [], [], []

    def txt(x, y, s, size, bold=False, gray=False):
        cur.append(f"{'0.4 g' if gray else '0 g'} BT /{'F2' if bold else 'F1'} {size} Tf {x:.1f} {y:.1f} Td ({_esc(s)}) Tj ET")

    def rect(x, y, w, h): cur.append(f"0.6 G 0.8 w {x:.1f} {y:.1f} {w:.1f} {h:.1f} re S")

    def line(x1, y1, x2, y2): cur.append(f"0 G 0.8 w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S")

    def add_img(durl):
        j = _jpeg(durl, media) if durl else None
        if not j: return None
        imgs.append(j); return (f"Im{len(imgs)}", j[1], j[2])

    def fit(im, x, y, bw, bh):
        k = min(bw / im[1], bh / im[2]); dw, dh = im[1] * k, im[2] * k
        cur.append(f"q {dw:.1f} 0 0 {dh:.1f} {x:.1f} {y + (bh - dh) / 2:.1f} cm /{im[0]} Do Q")
        return dw, dh

    def newpage():
        nonlocal cur
        pages.append("\n".join(cur)); cur = []
        return H - M

    numero = str(d.get("numero", ""))
    y = H - M
    logo = add_img(d.get("logo")); xt = M
    if logo: lw, _ = fit(logo, M, y - 48, 110, 48); xt = M + lw + 10
    solo = str(d.get("logo_solo")) == "1" and logo
    ty = y - 14
    if not solo: txt(xt, ty, d.get("taller", ""), 16, True); ty -= 12
    txt(xt, ty, d.get("titulo") or "Comprobante de ingreso de equipo", 8.5, False, True); ty -= 11
    for l in [x for x in str(d.get("taller_datos", "")).split("\n") if x.strip()][:4]:
        txt(xt, ty, l.strip(), 7.5, False, True); ty -= 9
    bw, bh = 190, 48; bx = W - M - bw
    rect(bx, y - bh, bw, bh)
    txt(bx + 8, y - 12, "N\xb0 DE ORDEN", 7, True, True)
    txt(bx + 8, y - 34, numero, 15, True)
    try:
        q = qr_matrix(numero); n = len(q); ms = 40.0 / (n + 4); qx, qy = bx + bw - 44, y - bh + 4
        cur.append("0 g")
        for r, row in enumerate(q):
            for c, ch in enumerate(row):
                if ch == "1": cur.append(f"{qx + (c + 2) * ms:.2f} {qy + (n - r + 1) * ms:.2f} {ms + .05:.2f} {ms + .05:.2f} re")
        cur.append("f")
    except Exception:
        pass
    y -= 58; line(M, y, W - M, y); y -= 8

    cond = _wrap(d.get("condiciones", ""), inner * 0.58, 6.5)
    foot = max(len(cond) * 8 + 12, 58)
    rows, pend = [], None
    for it in d.get("filas", []):
        k, v = it[0], str(it[1] if it[1] not in (None, "") else "-")
        full = bool(it[2]) if len(it) > 2 else False
        full = full or len(v) > 38
        if full:
            if pend: rows.append([pend]); pend = None
            rows.append([(k, v, True)])
        elif pend: rows.append([pend, (k, v, False)]); pend = None
        else: pend = (k, v, False)
    if pend: rows.append([pend])
    for row in rows:
        cells = [(k, _wrap(v, (inner if f else cw) - 12, 9)) for k, v, f in row]
        h = 10 + max(len(l) for _, l in cells) * 11 + 5
        if y - h < M + foot: y = newpage()
        for i, ((k, lines), (_, _, f)) in enumerate(zip(cells, row)):
            x = M + i * cw
            rect(x, y - h, inner if f else cw, h)
            txt(x + 5, y - 9, k.upper(), 6.5, True, True)
            for j, l in enumerate(lines): txt(x + 5, y - 20 - j * 11, l, 9)
        y -= h
    for i, l in enumerate(cond): txt(M, M + foot - 8 - i * 8, l, 6.5, False, True)
    x0 = M + inner * 0.62; lw = (inner * 0.38 - 14) / 2
    firma = add_img(d.get("firma"))
    for i, lab in enumerate((d.get("firma_label") or "Firma del cliente", "Firma del taller")):
        x = x0 + i * (lw + 14)
        if i == 0 and firma: fit(firma, x, M + 20, lw, 30)
        line(x, M + 18, x + lw, M + 18); txt(x + 4, M + 8, lab, 7, False, True)

    fotos = [f for f in (add_img(u) for u in (d.get("fotos") or [])) if f]
    if fotos:
        y = newpage(); txt(M, y - 12, "Fotos del equipo \xb7 Orden N\xb0 " + numero, 11, True)
        gap = 8; pw = (inner - 2 * gap) / 3; ph = (H - 2 * M - 26 - gap) / 2
        for idx, im in enumerate(fotos):
            pos = idx % 6
            if idx and pos == 0: y = newpage(); txt(M, y - 12, "Fotos del equipo \xb7 Orden N\xb0 " + numero, 11, True)
            x = M + (pos % 3) * (pw + gap); yy = H - M - 26 - (pos // 3 + 1) * ph - (pos // 3) * gap
            rect(x, yy, pw, ph); fit(im, x + 2, yy + 2, pw - 4, ph - 4)
    pages.append("\n".join(cur))

    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", None,
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"]
    xo = []
    for i, (b, w, h, c) in enumerate(imgs, 1):
        xo.append(f"/Im{i} {len(objs) + 1} 0 R")
        cs = {1: "/DeviceGray", 3: "/DeviceRGB"}.get(c, "/DeviceRGB")
        objs.append(f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace {cs} /BitsPerComponent 8 /Filter /DCTDecode /Length {len(b)} >>\nstream\n".encode() + b + b"\nendstream")
    kids = []
    for p in pages:
        pid = len(objs) + 1; kids.append(f"{pid} 0 R")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {W} {H}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> /XObject << {' '.join(xo)} >> >> /Contents {pid + 1} 0 R >>".encode())
        body = p.encode("latin-1", "replace")
        objs.append(f"<< /Length {len(body)} >>\nstream\n".encode() + body + b"\nendstream")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode()
    out = b"%PDF-1.4\n"; offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out)); out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for o in offs: out += f"{o:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF".encode()
    return out
