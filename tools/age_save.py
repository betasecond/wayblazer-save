"""EU-022 AGE save codec.

The on-disk executable is packed. This module follows the loader in the
running image: divide-and-xor, then Okumura LZSS, then two CRCs.
"""

import struct
import zlib
from pathlib import Path

HEADER = 0x214
POLY = 0x04C11DB7


def _crc_table():
    table = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            if c & 0x80000000:
                c = ((c << 1) ^ POLY) & 0xFFFFFFFF
            else:
                c = (c << 1) & 0xFFFFFFFF
        table.append(c)
    return table


_TABLE = _crc_table()


def crc_norm(blob: bytes) -> int:
    crc = 0xFFFFFFFF
    for b in blob:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _TABLE[((crc >> 24) ^ b) & 0xFF]
    return crc ^ 0xFFFFFFFF


def crc_reflected(blob: bytes) -> int:
    return zlib.crc32(blob) & 0xFFFFFFFF


def decrypt(body: bytes, count: int, key: int, divisor: int) -> bytes:
    steps = count >> 1
    out = bytearray(steps * 4)
    src = 0
    for i in range(steps):
        w0, w1 = struct.unpack_from("<II", body, src)
        d = divisor & 0xFFFF
        if d == 0 or w0 % d or w1 % d:
            raise ValueError(f"divisor rejected step {i}")
        word = (((w0 // d) << 16) + (w1 // d)) ^ key
        struct.pack_into("<I", out, i * 4, word & 0xFFFFFFFF)
        key = (key + 0x0B0B0B0B) & 0xFFFFFFFF
        divisor = (divisor + 0xB02) & 0xFFFFFFFF
        src += 8
    return bytes(out)


def encrypt(plain: bytes, key: int, divisor: int) -> bytes:
    if len(plain) % 4:
        raise ValueError("plain length must be a multiple of 4")
    n = len(plain) // 4
    out = bytearray(n * 8)
    o = 0
    for i in range(n):
        word = struct.unpack_from("<I", plain, i * 4)[0]
        combined = word ^ key
        d = divisor & 0xFFFF
        if d == 0:
            raise ValueError(f"divisor became 0 at step {i}")
        struct.pack_into(
            "<II",
            out,
            o,
            ((combined >> 16) & 0xFFFF) * d,
            (combined & 0xFFFF) * d,
        )
        o += 8
        key = (key + 0x0B0B0B0B) & 0xFFFFFFFF
        divisor = (divisor + 0xB02) & 0xFFFFFFFF
    return bytes(out)


def lzss_decompress(src: bytes) -> bytes:
    window = bytearray(0x1000)
    pos = 0xFEE
    out = bytearray()
    i = 0
    n = len(src)
    flags = 0
    while True:
        flags >>= 1
        if (flags & 0x100) == 0:
            if i >= n:
                break
            flags = src[i] | 0xFF00
            i += 1
        if i >= n:
            break
        b = src[i]
        i += 1
        if flags & 1:
            out.append(b)
            window[pos] = b
            pos = (pos + 1) & 0xFFF
        else:
            if i >= n:
                break
            b2 = src[i]
            i += 1
            offset = b | ((b2 & 0xF0) << 4)
            length = (b2 & 0xF) + 3
            for k in range(length):
                c = window[(offset + k) & 0xFFF]
                out.append(c)
                window[pos] = c
                pos = (pos + 1) & 0xFFF
    return bytes(out)


def lzss_compress(data: bytes) -> bytes:
    window = bytearray(0x1000)
    pos = 0xFEE
    index = {0: [0]}
    out = bytearray()
    i = 0
    n = len(data)

    def remember(src_i, wpos):
        if src_i + 2 >= n:
            return
        key = data[src_i] | (data[src_i + 1] << 8) | (data[src_i + 2] << 16)
        bucket = index.get(key)
        if bucket is None:
            index[key] = [wpos]
        else:
            bucket.append(wpos)
            if len(bucket) > 4:
                del bucket[0]

    def match_at(off):
        shadow = {}
        wpos = pos
        length = 0
        while length < 18 and i + length < n:
            src_pos = (off + length) & 0xFFF
            c = shadow[src_pos] if src_pos in shadow else window[src_pos]
            if c != data[i + length]:
                break
            shadow[wpos] = c
            wpos = (wpos + 1) & 0xFFF
            length += 1
        return length

    while i < n:
        flag_at = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if i >= n:
                break
            best_len = 0
            best_off = 0
            if i + 2 < n:
                key = data[i] | (data[i + 1] << 8) | (data[i + 2] << 16)
                for off in index.get(key, ()):
                    length = match_at(off)
                    if length > best_len:
                        best_len = length
                        best_off = off
                        if length == 18:
                            break
            if best_len >= 3:
                out.append(best_off & 0xFF)
                out.append(((best_off >> 4) & 0xF0) | ((best_len - 3) & 0xF))
                for k in range(best_len):
                    window[pos] = data[i + k]
                    remember(i + k, pos)
                    pos = (pos + 1) & 0xFFF
                i += best_len
            else:
                b = data[i]
                out.append(b)
                window[pos] = b
                remember(i, pos)
                pos = (pos + 1) & 0xFFF
                i += 1
                flags |= 1 << bit
        out[flag_at] = flags
    return bytes(out)


def load(path) -> tuple[bytes, int, int, bytearray]:
    """Return the original file, its key, its divisor, and the decoded plain.

    `path` may be a filesystem path or an already-read file.
    """
    if isinstance(path, (bytes, bytearray)):
        data = bytes(path)
    else:
        data = Path(path).read_bytes()
    if len(data) < HEADER + 20:
        raise ValueError("file is shorter than an AGE save header")
    count, crc_a, crc_b, key, divisor = struct.unpack_from("<5I", data, HEADER)
    cipher = data[HEADER + 20 : HEADER + 20 + (count << 2)]
    if len(cipher) != count << 2:
        raise ValueError("ciphertext is shorter than count")
    if crc_norm(cipher) != crc_a or crc_reflected(cipher) != crc_b:
        raise ValueError("outer checksum does not match")
    raw = decrypt(cipher, count, key, divisor)
    size, alloc, payload = struct.unpack_from("<III", raw, 0)
    if size != alloc:
        raise ValueError("wrapper sizes disagree")
    body = lzss_decompress(raw[12 : 12 + payload])
    if len(body) != size:
        raise ValueError(f"decompressed {len(body)} bytes, header says {size}")
    stored_a, stored_b = struct.unpack_from("<II", body, 0)
    if crc_norm(body[8:]) != stored_a or crc_reflected(body[8:]) != stored_b:
        raise ValueError("inner checksum does not match")
    return data, key, divisor, bytearray(body)


def dump(header: bytes, plain: bytes, key: int, divisor: int) -> bytes:
    """Pack plain back into a slot file. The 0x214-byte header is copied."""
    if len(header) < HEADER:
        raise ValueError("header is short")
    plain = bytearray(plain)
    body = bytes(plain)[8:]
    struct.pack_into("<II", plain, 0, crc_norm(body), crc_reflected(body))
    comp = lzss_compress(bytes(plain))
    if lzss_decompress(comp) != bytes(plain):
        raise ValueError("compressor round-trip failed")
    pad = (4 - (len(comp) % 4)) % 4
    wrapper = struct.pack("<III", len(plain), len(plain), len(comp)) + comp + bytes(pad)
    cipher = encrypt(wrapper, key, divisor)
    count = len(wrapper) // 2
    out = bytearray(header[:HEADER])
    out += struct.pack("<5I", count, crc_norm(cipher), crc_reflected(cipher), key, divisor)
    out += cipher
    return bytes(out)


def words(plain: bytes):
    if len(plain) % 4:
        raise ValueError("plain length must be a multiple of 4")
    return memoryview(plain).cast("I")
