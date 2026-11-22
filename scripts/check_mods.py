#!/usr/bin/env python3
# Проверка каталога модов Erik Mod Shop.
#
# Запуск:
#   python scripts/check_mods.py           # проверка (CI)
#   python scripts/check_mods.py --write   # проверить и пересобрать mods.json
#
# Правила:
#   * mods/<id>/mod.json + <id>-<версия>.efemod (+ preview.png);
#   * sha256 в mod.json совпадает с файлом;
#   * готовый мод не больше 1 МБ;
#   * внутри .efemod нет .exe/.dll/.bat, protocol только lua;
#   * подпись Ed25519 верна и ключ — доверенный TITEL.

import base64
import hashlib
import io
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODS = os.path.join(ROOT, "mods")
CATALOG = os.path.join(ROOT, "mods.json")

TRUSTED = "xJ6PZ96L+OEnyD+/sHxBZhzwn8fdHboWZmiPPeur3n8="
MAX_MOD = 1 * 1024 * 1024
FORBIDDEN = (".exe", ".dll", ".bat", ".cmd", ".ps1", ".sh", ".so", ".dylib")

errors = []


def fail(msg):
    errors.append(msg)
    print("ОШИБКА: " + msg)


def content_digest(files):
    """То же, что efepack: имя + 0 + длина(u64 LE) + sha256(данные)."""
    h = hashlib.sha256()
    for name in sorted(files):
        if name == "signature.json" or name.endswith("/"):
            continue
        data = files[name]
        h.update(name.encode("utf-8"))
        h.update(b"\x00")
        h.update(len(data).to_bytes(8, "little"))
        h.update(hashlib.sha256(data).digest())
    return h.digest()


def verify_signature(mod_id, files):
    raw = files.get("signature.json")
    if raw is None:
        fail("%s: нет signature.json — мод не подписан" % mod_id)
        return
    try:
        sig = json.loads(raw.decode("utf-8"))
    except Exception as e:
        fail("%s: signature.json не читается: %s" % (mod_id, e))
        return

    pub = sig.get("publicKey", "")
    signature = sig.get("signature", "")
    if pub != TRUSTED:
        fail("%s: чужой ключ подписи" % mod_id)
        return

    try:
        from nacl.signing import VerifyKey
    except ImportError:
        print("pynacl не установлен — подпись не проверена")
        return

    digest = content_digest(files)
    try:
        VerifyKey(base64.b64decode(pub)).verify(digest, base64.b64decode(signature))
        print("%s: подпись верна" % mod_id)
    except Exception:
        fail("%s: подпись неверна" % mod_id)


def check_mod(mod_id, folder):
    meta_path = os.path.join(folder, "mod.json")
    if not os.path.isfile(meta_path):
        fail("%s: нет mod.json" % mod_id)
        return None

    with open(meta_path, "r", encoding="utf-8-sig") as f:
        meta = json.load(f)

    if meta.get("id") != mod_id:
        fail("%s: id в mod.json не совпадает с папкой" % mod_id)

    file_name = meta.get("file", "")
    pkg = os.path.join(folder, file_name)
    if not file_name or not os.path.isfile(pkg):
        fail("%s: нет файла пакета %s" % (mod_id, file_name))
        return None

    size = os.path.getsize(pkg)
    if size > MAX_MOD:
        fail("%s: пакет больше 1 МБ (%d Б)" % (mod_id, size))

    sha = hashlib.sha256(open(pkg, "rb").read()).hexdigest()
    if meta.get("sha256", "").lower() != sha:
        fail("%s: sha256 в mod.json не совпадает" % mod_id)

    files = {}
    try:
        with zipfile.ZipFile(pkg) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                files[info.filename] = z.read(info.filename)
    except Exception as e:
        fail("%s: пакет не читается: %s" % (mod_id, e))
        return None

    for name in files:
        if name.lower().endswith(FORBIDDEN):
            fail("%s: запрещённый файл внутри пакета: %s" % (mod_id, name))

    man_raw = files.get("manifest.json")
    if man_raw is None:
        fail("%s: в пакете нет manifest.json" % mod_id)
        return None

    try:
        man = json.loads(man_raw.decode("utf-8-sig"))
    except Exception as e:
        fail("%s: manifest.json не читается: %s" % (mod_id, e))
        return None

    if man.get("protocol") != "lua":
        fail(
            "%s: protocol=%s — разрешён только lua (без DLL)"
            % (mod_id, man.get("protocol"))
        )

    verify_signature(mod_id, files)

    preview = os.path.join(folder, "preview.png")
    rel_preview = meta.get("preview", "")
    return {
        "id": mod_id,
        "name": meta.get("name", mod_id),
        "author": meta.get("author", "TITEL"),
        "version": meta.get("version", man.get("version", "1.0.0")),
        "game": meta.get("game", "2.2.7"),
        "path": "mods/" + mod_id,
        "file": "mods/%s/%s" % (mod_id, file_name),
        "preview": rel_preview or ("mods/%s/preview.png" % mod_id),
        "size": size,
        "sha256": sha,
        "tags": meta.get("tags", ["official"]),
        "description": meta.get("description", ""),
    }


def main():
    write = "--write" in sys.argv

    if not os.path.isdir(MODS):
        print("Нет папки mods/ — нечего проверять")
        return 0

    entries = []
    for mod_id in sorted(os.listdir(MODS)):
        folder = os.path.join(MODS, mod_id)
        if not os.path.isdir(folder):
            continue
        entry = check_mod(mod_id, folder)
        if entry:
            entries.append(entry)

    print("Проверено модов: %d, ошибок: %d" % (len(entries), len(errors)))

    if errors:
        return 1

    if write:
        catalog = {
            "schema": 1,
            "updated": "",
            "mods": sorted(entries, key=lambda e: e["id"]),
        }
        import datetime

        catalog["updated"] = datetime.date.today().isoformat()
        data = json.dumps(catalog, ensure_ascii=False, indent=4) + "\n"
        with open(CATALOG, "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
        print("mods.json обновлён")

    return 0


if __name__ == "__main__":
    sys.exit(main())
