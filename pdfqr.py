"""QR (nivel M) y comprobante PDF, sin dependencias externas."""
import base64, os, struct
from media import MEDIA, MEDIA_RE


# ------------------------------------------------------------------ QR (byte mode, nivel M)
_ECC = [0, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26]
_BLK = [0, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5]


def _gmul(x, y):
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_gen(deg):
    r = [0] * (deg - 1) + [1]; root = 1
    for _ in range(deg):
        for j in range(deg):
            r[j] = _gmul(r[j], root)
            if j + 1 < deg: r[j] ^= r[j + 1]
        root = _gmul(root, 2)
    return r


def _rs_div(data, gen):
    res = [0] * len(gen)
    for b in data:
        f = b ^ res.pop(0); res.append(0)
        for i, c in enumerate(gen): res[i] ^= _gmul(c, f)
    return res


def _raw_modules(v):
    r = (16 * v + 128) * v + 64
    if v >= 2:
        na = v // 7 + 2; r -= (25 * na - 10) * na - 55
        if v >= 7: r -= 36
    return r


def qr_matrix(text):
    data = text.encode("utf-8")
    ver = next((v for v in range(1, 11) if len(data) <= _raw_modules(v) // 8 - _ECC[v] * _BLK[v] - 3), None)
    if ver is None: raise ValueError("texto demasiado largo para el QR")
    cap = _raw_modules(ver) // 8 - _ECC[ver] * _BLK[ver]
    bits = [0, 1, 0, 0]
    cc = 8 if ver < 10 else 16
    bits += [(len(data) >> i) & 1 for i in range(cc - 1, -1, -1)]
    for b in data: bits += [(b >> i) & 1 for i in range(7, -1, -1)]
    bits += [0] * min(4, cap * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)
    cw = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(cw) < cap:
        cw.append(pad); pad ^= 0xEC ^ 0x11
    nb, ecl = _BLK[ver], _ECC[ver]
    raw = _raw_modules(ver) // 8
    nshort = nb - raw % nb; slen = raw // nb
    gen = _rs_gen(ecl); blocks = []; k = 0
    for i in range(nb):
        dat = cw[k:k + slen - ecl + (0 if i < nshort else 1)]; k += len(dat)
        ecc = _rs_div(dat, gen)
        if i < nshort: dat = dat + [0]
        blocks.append(dat + ecc)
    final = []
    for i in range(len(blocks[0])):
        for j, blk in enumerate(blocks):
            if i != slen - ecl or j >= nshort: final.append(blk[i])
    size = ver * 4 + 17
    mod = [[False] * size for _ in range(size)]
    fn = [[False] * size for _ in range(size)]

    def setf(x, y, v):
        mod[y][x] = bool(v); fn[y][x] = True

    for i in range(size):
        setf(6, i, i % 2 == 0); setf(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < size and 0 <= y < size: setf(x, y, max(abs(dx), abs(dy)) not in (2, 4))
    if ver > 1:
        na = ver // 7 + 2
        step = (ver * 4 + na * 2 + 1) // (na * 2 - 2) * 2
        pos = sorted([size - 7 - i * step for i in range(na - 1)] + [6])
        for i, px in enumerate(pos):
            for j, py in enumerate(pos):
                if (i == 0 and j == 0) or (i == 0 and j == na - 1) or (i == na - 1 and j == 0): continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3): setf(px + dx, py + dy, max(abs(dx), abs(dy)) != 1)

    def fmt(mask):
        data_ = mask  # nivel M = 00
        rem = data_
        for _ in range(10): rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        b = ((data_ << 10) | rem) ^ 0x5412
        g = lambda i: (b >> i) & 1
        for i in range(6): setf(8, i, g(i))
        setf(8, 7, g(6)); setf(8, 8, g(7)); setf(7, 8, g(8))
        for i in range(9, 15): setf(14 - i, 8, g(i))
        for i in range(8): setf(size - 1 - i, 8, g(i))
        for i in range(8, 15): setf(8, size - 15 + i, g(i))
        setf(8, size - 8, True)

    fmt(0)
    if ver >= 7:
        rem = ver
        for _ in range(12): rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        b = (ver << 12) | rem
        for i in range(18):
            a, c2 = size - 11 + i % 3, i // 3
            setf(a, c2, (b >> i) & 1); setf(c2, a, (b >> i) & 1)
    i = 0; total = len(final) * 8
    for right in range(size - 1, 0, -2):
        if right == 6: right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                y = size - 1 - vert if ((right + 1) & 2) == 0 else vert
                if not fn[y][x] and i < total:
                    mod[y][x] = ((final[i >> 3] >> (7 - (i & 7))) & 1) == 1; i += 1
    masks = [lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
             lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
             lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
             lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0]

    def penalty(m):
        p = 0
        for g in (m, [list(r) for r in zip(*m)]):
            for row in g:
                run = 1
                for a in range(1, size):
                    if row[a] == row[a - 1]:
                        run += 1
                        if run == 5: p += 3
                        elif run > 5: p += 1
                    else: run = 1
        for y in range(size - 1):
            for x in range(size - 1):
                if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]: p += 3
        return p

    best = None
    for mk in range(8):
        m = [row[:] for row in mod]
        for y in range(size):
            for x in range(size):
                if not fn[y][x] and masks[mk](x, y): m[y][x] = not m[y][x]
        pen = penalty(m)
        if best is None or pen < best[0]: best = (pen, mk, m)
    _, mk, m = best
    mod = m; fmt(mk)
    return ["".join("1" if c else "0" for c in row) for row in mod]


# ------------------------------------------------------------------ PDF
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


def _jpeg(durl):
    """dataURL JPEG -> (bytes, ancho, alto, componentes) o None"""
    try:
        m = MEDIA_RE.match(durl) if durl.startswith("/media/") else None
        if durl.startswith("/media/"):
            with open(os.path.join(MEDIA, m.group(1), m.group(2)), "rb") as fh: b = fh.read()
        else:
            b = base64.b64decode(durl.split(",", 1)[1])
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


def pdf_comprobante(d):
    mm = 72 / 25.4
    W = round(float(d.get("ancho_mm") or 210) * mm, 2); H = round(float(d.get("alto_mm") or 148) * mm, 2)
    M = 26; inner = W - 2 * M; cw = inner / 2
    pages, cur, imgs = [], [], []

    def txt(x, y, s, size, bold=False, gray=False):
        cur.append(f"{'0.4 g' if gray else '0 g'} BT /{'F2' if bold else 'F1'} {size} Tf {x:.1f} {y:.1f} Td ({_esc(s)}) Tj ET")

    def rect(x, y, w, h): cur.append(f"0.6 G 0.8 w {x:.1f} {y:.1f} {w:.1f} {h:.1f} re S")

    def line(x1, y1, x2, y2): cur.append(f"0 G 0.8 w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S")

    def add_img(durl):
        j = _jpeg(durl) if durl else None
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
