"""M6 연결표 빌드 재현 (등록 v3 §5) — 다시 빌드한 APK 와 기존 APK 를 항목별로 비교한다 (기록만, 판정 이름 = 프롬프트 1단계).

  py -3 -X utf8 s26/tools/mixreq/m6_apk_compare.py <old.apk> <rebuilt.apk> [--out compare.json]

출력: 두 APK 파일 SHA-256 · zip 항목별 (이름 · 크기 · CRC · 내용 SHA-256) 같음/다름 · classes*.dex SHA 비교 · 서명 블록 밖 차이 요약.
결론 문구: 파일 SHA 같음 → 「빌드 재현 확인」 · 다르면 「빌드 재현 미확인 (작업 기록 · 세션 기록상 대응)」 +
  classes*.dex 가 전부 같으면 "dex 같음 — 서명/패키징 차이".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def entries(path: Path) -> dict[str, dict]:
    out = {}
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            data = z.read(info.filename)
            out[info.filename] = dict(size=info.file_size, crc=info.CRC, sha256=hashlib.sha256(data).hexdigest(), compress_type=info.compress_type)
    return out


def compare(old: Path, new: Path) -> dict:
    a, b = entries(old), entries(new)
    names = sorted(set(a) | set(b))
    differ = [n for n in names if n in a and n in b and a[n]["sha256"] != b[n]["sha256"]]
    only_old = [n for n in names if n not in b]
    only_new = [n for n in names if n not in a]
    dex = sorted(n for n in names if n.startswith("classes") and n.endswith(".dex"))
    dex_rows = [dict(name=n, old=a.get(n, {}).get("sha256"), new=b.get(n, {}).get("sha256"),
                     equal=a.get(n, {}).get("sha256") == b.get(n, {}).get("sha256") and n in a and n in b) for n in dex]
    sig = [n for n in differ + only_old + only_new if n.startswith("META-INF/")]
    non_sig = [n for n in differ + only_old + only_new if not n.startswith("META-INF/")]
    file_equal = sha256_file(old) == sha256_file(new)
    dex_equal = bool(dex_rows) and all(r["equal"] for r in dex_rows)
    if file_equal:
        verdict = "빌드 재현 확인"
    else:
        verdict = "빌드 재현 미확인 (작업 기록 · 세션 기록상 대응)" + (" · dex 같음 — 서명/패키징 차이" if dex_equal else " · dex 다름")
    return dict(schema="s26-m6-apk-compare-v1", old=dict(path=old.name, sha256=sha256_file(old), bytes=old.stat().st_size, entries=len(a)),
                new=dict(path=new.name, sha256=sha256_file(new), bytes=new.stat().st_size, entries=len(b)),
                file_equal=file_equal, dex=dex_rows, dex_equal=dex_equal, entries_differ=differ, only_old=only_old, only_new=only_new,
                differ_outside_meta_inf=non_sig, differ_meta_inf=sig, verdict=verdict)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    result = compare(args.old, args.new)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(json.dumps(dict(verdict=result["verdict"], file_equal=result["file_equal"], dex_equal=result["dex_equal"],
                          differ_outside_meta_inf=result["differ_outside_meta_inf"][:20], differ_meta_inf=result["differ_meta_inf"]), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
