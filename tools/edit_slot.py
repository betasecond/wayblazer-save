"""Change gold and the first three character levels in one EU-022 slot.

The level dwords are 马克, 苏菲亚, 瑞理. Zeros after them are left alone.
Experience and equipment are not written.

The script refuses to edit unless the dwords around the wallet are still
0, 569, 360, gold, 190. That is the pattern from this build, not a guess
from a nearby 180.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import age_save

GOLD = 9873
GOLD_COPY = (76526, 76527)
LEVELS = 1246717
NAMES = ("马克", "苏菲亚", "瑞理")


def require_wallet(dwords):
    left = [dwords[GOLD - 3], dwords[GOLD - 2], dwords[GOLD - 1]]
    right = dwords[GOLD + 1]
    if left != [0, 569, 360] or right != 190:
        raise SystemExit(
            f"wallet neighbors are {left} / {right}, expected [0, 569, 360] / 190"
        )


def show(dwords):
    gold = dwords[GOLD]
    party = [dwords[LEVELS + i] for i in range(8)]
    exp = [dwords[LEVELS + 100 + i] for i in range(3)]
    print(f"gold {gold}")
    print("levels", ", ".join(f"{n}={v}" for n, v in zip(NAMES, party)))
    print("later ", party[3:])
    print("exp  ", exp)


def edit(path, gold, level, output):
    data, key, divisor, plain = age_save.load(path)
    dwords = age_save.words(plain)
    require_wallet(dwords)
    print("before")
    show(dwords)
    if gold is None and level is None:
        return
    old_gold = dwords[GOLD]
    if gold is not None:
        if not 0 <= gold <= 2_000_000_000:
            raise SystemExit("gold is out of range")
        dwords[GOLD] = gold
        for idx in GOLD_COPY:
            if dwords[idx] == old_gold:
                dwords[idx] = gold
            else:
                print(f"left dword {idx} at {dwords[idx]}")
    if level is not None:
        if not 1 <= level <= 99:
            raise SystemExit("level must be 1..99")
        for i, name in enumerate(NAMES):
            cur = dwords[LEVELS + i]
            if not 1 <= cur <= 99:
                raise SystemExit(f"{name} is {cur}, not an existing level")
            dwords[LEVELS + i] = level
    print("after")
    show(dwords)
    packed = age_save.dump(data[: age_save.HEADER], bytes(plain), key, divisor)
    # Read it back before replacing anything.
    tmp = Path(str(output) + ".partial")
    tmp.write_bytes(packed)
    _, _, _, check = age_save.load(tmp)
    if bytes(check[8:]) != bytes(plain[8:]):
        tmp.unlink(missing_ok=True)
        raise SystemExit("reloaded file does not match the edited plain")
    tmp.replace(output)
    print("wrote", output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slot", type=Path)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--gold", type=int)
    parser.add_argument("--level", type=int)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    if args.show or (args.gold is None and args.level is None):
        _, _, _, plain = age_save.load(args.slot)
        require_wallet(age_save.words(plain))
        show(age_save.words(plain))
        return
    output = args.output or args.slot.with_name(args.slot.name + ".edited")
    if output.resolve() == args.slot.resolve():
        raise SystemExit("refusing to overwrite the slot; pass a different -o")
    edit(args.slot, args.gold, args.level, output)


if __name__ == "__main__":
    main()
