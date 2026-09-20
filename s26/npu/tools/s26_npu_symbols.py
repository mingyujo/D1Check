#!/usr/bin/env python3
"""ELF dynamic-symbol checker for Samsung ENN public API libraries.

Question answered: does the phone's libenn_public_api_cpp.so export what LiteRT's Samsung
dispatch (litert/vendors/samsung/dispatch/enn_manager.cc, main 2026-09) needs?

LiteRT does a plain dlsym() on C names ("EnnInitialize" ...), 15 REQUIRED + 5 OPTIONAL.
Older ENN runtimes (e.g. ENN_VERSION_2.4.x on Galaxy S26 One UI 8.5) export ONLY the C++
namespaced form (_ZN3enn3api13EnnInitializeEv = enn::api::EnnInitialize()), which dlsym("EnnInitialize")
will NOT find. So this tool reports three things per function:
    C    plain C symbol present            -> LiteRT dispatch can bind
    C++  only enn::api:: mangled present   -> function exists, but LiteRT (as written) cannot bind
    -    absent in any form                -> newer ENN API than this firmware

Usage:
    python s26_npu_symbols.py <libenn_public_api_cpp.so> [<libenn_user.samsung_slsi.so> ...] [--json out.json]
    Give every library in the dlopen dependency chain: bionic dlsym(handle) also searches DT_NEEDED
    dependencies, so plain C symbols living in libenn_user.samsung_slsi.so count when
    libenn_public_api_cpp.so NEEDs it (it does on S26 One UI 8.5).

Standard library only. ELF64 little-endian (arm64-v8a, x86_64). Output is ASCII on purpose
(Windows cp949 consoles choke on non-ASCII).
"""
import json
import re
import struct
import sys
from pathlib import Path

REQUIRED = [
    "EnnInitialize",
    "EnnCreateBufferFromFdWithOffset",
    "EnnCreateBufferCache",
    "EnnBufferCommit",
    "EnnGetBuffersInfo",
    "EnnSetBufferByIndex",
    "EnnReleaseBuffer",
    "EnnExecuteModel",
    "EnnBufferUncommit",
    "EnnUnsetBuffers",
    "EnnCloseModel",
    "EnnDeinitialize",
    "EnnAllocateAllBuffers",
    "EnnSetPreferencePerfMode",
    "EnnSetPreferencePerfConfigId",
]
OPTIONAL = [
    "EnnOpenModelFromMemory",
    "EnnOpenModelFromMemoryWithWeight",
    "EnnOpenModelFromFdWithWeight",
    "EnnOpenModelWithFileOpenFdWeight",
    "EnnOpenModelWithFileOpenFd",
]

SHT_DYNSYM = 11
STB_GLOBAL, STB_WEAK = 1, 2
SHN_UNDEF = 0
MANGLED_RE = re.compile(r"^_ZN3enn3api(\d+)")  # _ZN3enn3api13EnnInitializeEv -> length 13 -> EnnInitialize


def demangle_enn(sym: str) -> str | None:
    """enn::api::<Name> Itanium mangling: _ZN3enn3api<len><Name>E... -> <Name> (uses the length prefix)."""
    m = MANGLED_RE.match(sym)
    if not m:
        return None
    n = int(m.group(1))
    name = sym[m.end():m.end() + n]
    return name if name.startswith("Enn") else None


def _sections(data: bytes):
    if data[:4] != b"\x7fELF":
        raise ValueError("not an ELF file")
    if data[4] != 2:
        raise ValueError("only ELF64 is supported (32-bit file)")
    if data[5] != 1:
        raise ValueError("only little-endian is supported")
    (e_shoff,) = struct.unpack_from("<Q", data, 0x28)
    e_shentsize, e_shnum = struct.unpack_from("<HH", data, 0x3A)
    out = []
    for i in range(e_shnum):
        out.append(struct.unpack_from("<IIQQQQIIQQ", data, e_shoff + i * e_shentsize))
    return out  # (name, type, flags, addr, offset, size, link, info, align, entsize)


def read_dynsym(path: Path):
    """Return {name: (value, size, shndx)} for defined GLOBAL/WEAK dynamic symbols."""
    data = path.read_bytes()
    secs = _sections(data)
    defined = {}
    for sh in secs:
        if sh[1] != SHT_DYNSYM or sh[9] == 0:
            continue
        stro, strs = secs[sh[6]][4], secs[sh[6]][5]
        strtab = data[stro:stro + strs]
        for j in range(sh[5] // sh[9]):
            st_name, st_info, _o, st_shndx, st_value, st_size = struct.unpack_from(
                "<IBBHQQ", data, sh[4] + j * sh[9])
            if st_shndx == SHN_UNDEF or (st_info >> 4) not in (STB_GLOBAL, STB_WEAK):
                continue
            end = strtab.find(b"\x00", st_name)
            defined[strtab[st_name:end].decode("ascii", "replace")] = (st_value, st_size, st_shndx)
    return defined


def enn_version(path: Path, defined) -> str | None:
    """Follow the enn::ver_str pointer (_ZN3enn7ver_strE) to its C string, if present."""
    sym = defined.get("_ZN3enn7ver_strE")
    if not sym:
        return None
    data = path.read_bytes()
    secs = _sections(data)
    value, size, shndx = sym
    try:
        sec = secs[shndx]
        raw = data[sec[4] + (value - sec[3]):][:size]
        if size == 8:
            (p,) = struct.unpack_from("<Q", raw)
            for s in secs:
                if s[3] <= p < s[3] + s[5]:
                    fo = s[4] + (p - s[3])
                    return data[fo:data.find(b"\x00", fo)].decode("ascii", "replace")
        return raw.split(b"\x00")[0].decode("ascii", "replace")
    except Exception:  # noqa: BLE001
        return None


def classify(defined):
    """name -> 'C' | 'C++' | '-' for every Enn* function seen in either form."""
    plain = {n for n in defined if n.startswith("Enn")}
    mangled = {}
    for n in defined:
        d = demangle_enn(n)
        if d:
            mangled[d] = n
    names = sorted(plain | set(mangled) | set(REQUIRED) | set(OPTIONAL))
    return {n: ("C" if n in plain else "C++" if n in mangled else "-") for n in names}, plain, mangled


def needed(path: Path):
    """DT_NEEDED entries (which libraries this one loads), for the dependency-tree note."""
    data = path.read_bytes()
    secs = _sections(data)
    out = []
    for sh in secs:
        if sh[1] != 6:  # SHT_DYNAMIC
            continue
        strsec = secs[sh[6]]
        strtab = data[strsec[4]:strsec[4] + strsec[5]]
        for j in range(sh[5] // 16):
            tag, val = struct.unpack_from("<qQ", data, sh[4] + j * 16)
            if tag == 1:  # DT_NEEDED
                out.append(strtab[val:strtab.find(b"\x00", val)].decode("ascii", "replace"))
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    out_json = Path(argv[argv.index("--json") + 1]) if "--json" in argv else None
    paths = [Path(a) for a in argv[1:] if a != "--json" and (out_json is None or Path(a) != out_json)]
    paths = [p for p in paths if p.suffix != ".json"]

    # Several files = one dlopen dependency tree: bionic dlsym(handle, name) searches the opened
    # library AND its DT_NEEDED dependencies, so a plain C symbol in libenn_user.samsung_slsi.so
    # is reachable through dlopen("libenn_public_api_cpp.so") if the latter NEEDs the former.
    per_file = []
    defined = {}
    for p in paths:
        try:
            d = read_dynsym(p)
        except Exception as e:  # noqa: BLE001
            print(f"[X] cannot read {p}: {e}")
            return 1
        c, pl, mg = classify(d)
        per_file.append((p, d, c, pl, mg, enn_version(p, d), needed(p)))
        for k, v in d.items():
            defined.setdefault(k, v)
    cls, plain, mangled = classify(defined)
    ver = " / ".join(f"{p.name}: {v or '?'}" for p, _d, _c, _pl, _mg, v, _n in per_file)
    path = paths[0]

    for p, d, c, pl, mg, v, nd in per_file:
        print(f"file: {p}  ({p.stat().st_size:,} B)  ENN version: {v or '(not found)'}")
        print(f"  defined dynamic symbols: {len(d)} | plain C Enn*: {len(pl)} | C++ enn::api::Enn*: {len(mg)}")
        print(f"  NEEDED: {', '.join(nd) if nd else '-'}")
    if len(per_file) > 1:
        print("combined view (dlsym searches the dependency tree):")
    print()
    print("REQUIRED by LiteRT Samsung dispatch (15)   [C]=bindable  [C++]=exists but not bindable  [-]=absent")
    req_c = req_cxx = req_absent = 0
    for n in REQUIRED:
        tag = cls[n]
        req_c += tag == "C"; req_cxx += tag == "C++"; req_absent += tag == "-"
        print(f"  [{tag:>3}] {n}")
    print("OPTIONAL (need at least one bindable)")
    opt_c = 0
    for n in OPTIONAL:
        tag = cls[n]
        opt_c += tag == "C"
        print(f"  [{tag:>3}] {n}")
    print()
    print("all Enn* functions exported (combined):")
    for n, tag in cls.items():
        if tag != "-":
            print(f"  [{tag:>3}] {n}")
    print()
    if req_c == len(REQUIRED) and opt_c >= 1:
        verdict = "PASS"
        note = "LiteRT libLiteRtDispatch_Samsung.so can dlsym everything it needs on this firmware."
    elif req_absent == 0 and req_cxx > 0:
        verdict = "CXX_ONLY"
        note = ("all required functions exist but only as C++ enn::api:: symbols; LiteRT (plain dlsym) "
                "cannot bind them as written -> path A blocked on this firmware, path B (ENNDelegate) unaffected.")
    else:
        verdict = "FAIL"
        missing = [n for n in REQUIRED if cls[n] == "-"]
        note = (f"{len(missing)} required function(s) absent in any form: {', '.join(missing)} "
                f"-> this firmware's ENN API ({ver or 'unknown'}) is older than what LiteRT targets; "
                "path A needs a newer firmware (re-run after OS update), path B (ENNDelegate) unaffected.")
    print(f"VERDICT: {verdict}  (required: C={req_c}, C++only={req_cxx}, absent={req_absent}; optional bindable={opt_c})")
    print("  -> " + note)
    if out_json:
        out_json.write_text(json.dumps({
            "files": [str(x) for x in paths], "enn_version": ver,
            "needed": {x.name: nd for x, _d, _c, _pl, _mg, _v, nd in per_file},
            "verdict": verdict, "note": note,
            "required": {n: cls[n] for n in REQUIRED}, "optional": {n: cls[n] for n in OPTIONAL},
            "exported": {n: t for n, t in cls.items() if t != "-"},
        }, indent=2), encoding="utf-8")
        print(f"json: {out_json}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
