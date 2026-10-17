"""Round-trip the codec without a save file."""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import age_save


def test_cipher():
    plain = bytes(range(64))
    key, divisor = 0x1ABF0C57, 0x777
    cipher = age_save.encrypt(plain, key, divisor)
    back = age_save.decrypt(cipher, len(cipher) // 4, key, divisor)
    if back != plain:
        raise SystemExit("cipher round-trip failed")


def test_lzss():
    piece = b"AGE" * 100 + bytes(range(256)) + b"\x00" * 50 + b"levels 4,1,4"
    comp = age_save.lzss_compress(piece)
    if age_save.lzss_decompress(comp) != piece:
        raise SystemExit("lzss round-trip failed")


def test_container():
    body = b"wallet" * 300 + b"\x00" * 20
    plain = struct.pack("<II", 0, 0) + body
    header = bytes(age_save.HEADER)
    packed = age_save.dump(header, plain, 0x11111111, 0x777)
    _, _, _, back = age_save.load(packed)
    if back[8:] != body:
        raise SystemExit("container round-trip failed")


if __name__ == "__main__":
    test_cipher()
    test_lzss()
    test_container()
    print("ok")
