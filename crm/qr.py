"""Generador de códigos QR (byte mode, corrección de errores nivel M, versiones 1 a 10). Sin dependencias."""


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
