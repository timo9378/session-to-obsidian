"""s2o CLI:把一場 Claude Code / Copilot session 匯入 Obsidian。

  s2o import <file> --vault <vault根> [--lang en|zh-TW] [--cluster claude_cli|time] ...
  s2o index --vault <vault根>
"""
from __future__ import annotations
import argparse
import glob
import hashlib
import json
import os
import shutil
import sys

from . import adapters, cluster as clustermod, i18n, index as indexmod, parse, render
from .slugs import session_slug


def _paths(vault, subdir, attachments, slug):
    return (os.path.join(vault, subdir, slug),
            os.path.join(vault, attachments, slug),
            attachments)


def _read_origin(md_path) -> str | None:
    """讀 .md frontmatter 的 originSessionId(值可能被引號包,做 json 還原)。"""
    try:
        with open(md_path, encoding="utf-8") as f:
            if f.readline().strip() != "---":
                return None
            for _ in range(25):
                ln = f.readline()
                if not ln or ln.strip() == "---":
                    break
                if ln.startswith("originSessionId:"):
                    v = ln.split(":", 1)[1].strip()
                    try:
                        return json.loads(v)        # 去引號 / unescape
                    except Exception:
                        return v.strip('"')
    except Exception:
        pass
    return None


def _folder_origin(folder) -> str | None:
    """folder 內第一個 .md 的 originSessionId(無則 None)。"""
    mds = glob.glob(os.path.join(folder, "*.md"))
    return _read_origin(mds[0]) if mds else None


def _under(child, parent) -> bool:
    """child 確實在 parent 之下(去重刪檔的安全邊界,防誤刪 vault 外)。"""
    try:
        return os.path.commonpath([os.path.abspath(child), os.path.abspath(parent)]) == \
            os.path.abspath(parent)
    except Exception:
        return False


def _dedupe(sessions_dir, vault, attachments, origin_id) -> list[str]:
    """匯入前先刪同源舊資料夾(免標題變動產生重複)。只刪 sessions_dir 之下的。"""
    if not origin_id:
        return []
    removed = []
    for md in glob.glob(os.path.join(sessions_dir, "*", "*.md")):
        if _read_origin(md) != origin_id:
            continue
        folder = os.path.dirname(md)
        slug = os.path.basename(folder)
        att = os.path.join(vault, attachments, slug)
        if _under(folder, sessions_dir):
            shutil.rmtree(folder, ignore_errors=True)
            if _under(att, os.path.join(vault, attachments)):
                shutil.rmtree(att, ignore_errors=True)
            removed.append(slug)
    return removed


def cmd_import(a) -> int:
    if not os.path.isfile(a.file):
        print(f"找不到 session 檔:{a.file}", file=sys.stderr)
        return 1
    if not os.path.isdir(a.vault):
        print(f"--vault 不是有效目錄:{a.vault}", file=sys.stderr)
        return 1
    try:
        records, meta = adapters.load(a.file, a.source)
    except Exception as e:
        print(f"讀取/解析失敗({a.source}):{e}", file=sys.stderr)
        return 1
    steps = parse.parse_records(records, with_images=a.images)
    if not steps:
        print("沒有可匯入的步驟(空 session?)", file=sys.stderr)
        return 1

    backend = a.cluster
    try:
        clustering = clustermod.cluster(steps, backend=backend, model=a.model,
                                        timeout=a.timeout, lang=a.lang)
    except clustermod.ClusterError as e:
        if backend == "claude_cli" and not a.no_fallback:
            print(f"⚠ 分群({backend})失敗:{e}\n  → 退回時間分段(--cluster time)", file=sys.stderr)
            clustering = clustermod.cluster(steps, backend="time", lang=a.lang)
        else:
            print(f"分群失敗:{e}", file=sys.stderr)
            return 2

    title = clustering["title"]
    source = meta.get("source", "session")
    origin_id = (meta.get("session_id") or os.path.splitext(os.path.basename(a.file))[0]).strip()
    slug = a.slug or session_slug(meta.get("date", ""), source, title)
    sessions_dir = os.path.join(a.vault, a.subdir)
    removed = _dedupe(sessions_dir, a.vault, a.attachments, origin_id)

    out_dir, attach_abs, attach_rel = _paths(a.vault, a.subdir, a.attachments, slug)
    if _folder_origin(out_dir) not in (None, origin_id):     # 不同場撞同標題 → 加後綴
        slug = f"{slug}-{hashlib.sha1(origin_id.encode()).hexdigest()[:6]}"
        out_dir, attach_abs, attach_rel = _paths(a.vault, a.subdir, a.attachments, slug)

    stats = render.render(steps, clustering, out_dir, slug, attach_abs, attach_rel,
                          noimg=not a.images, origin_id=origin_id, source=source, lang=a.lang)
    if removed:
        print(f"  (取代同源舊版:{', '.join(removed)})")
    print(f"✓ {slug}")
    print(f"  {stats['steps']} steps · {stats['topics']} topics · {stats['images']} img · "
          f"{backend} · {a.lang} · {title}")

    if not a.no_index:
        ix = indexmod.build_index(sessions_dir, lang=a.lang)
        print(f"  INDEX.md: {ix['sessions']} sessions · {ix['topics']} topics")
    return 0


def cmd_index(a) -> int:
    ix = indexmod.build_index(os.path.join(a.vault, a.subdir), lang=a.lang)
    print(f"✓ INDEX.md: {ix['sessions']} sessions · {ix['topics']} topics")
    return 0


def main(argv=None) -> int:
    env_vault = os.environ.get("S2O_VAULT")
    env_lang = os.environ.get("S2O_LANG", i18n.DEFAULT_LANG)
    p = argparse.ArgumentParser(prog="s2o", description="Claude Code / Copilot session → Obsidian topic recap")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--vault", default=env_vault, required=env_vault is None,
                        help="Obsidian vault root (or set env S2O_VAULT)")
        sp.add_argument("--subdir", default="90-Meta/sessions", help="where sessions live (vault-relative)")
        sp.add_argument("--lang", default=env_lang, choices=i18n.LANGS,
                        help=f"output language (default {env_lang}; or env S2O_LANG)")

    pi = sub.add_parser("import", help="import one session")
    pi.add_argument("file", help="session jsonl (Claude native or Copilot append-log)")
    common(pi)
    pi.add_argument("--source", default="auto", choices=["auto", "claude", "copilot"])
    pi.add_argument("--cluster", default="claude_cli", choices=["claude_cli", "time"],
                    help="clustering backend (claude_cli = host Claude headless; time = time-segment fallback)")
    pi.add_argument("--model", default=None, help="model for claude_cli backend (default: your CC setting)")
    pi.add_argument("--timeout", type=int, default=180, help="claude_cli timeout seconds")
    pi.add_argument("--no-fallback", action="store_true", help="don't fall back to time on claude_cli failure")
    pi.add_argument("--attachments", default="_attachments/sessions", help="where images go (vault-relative)")
    pi.add_argument("--images", action="store_true", help="extract screenshots (default: text-only)")
    pi.add_argument("--slug", default=None, help="override auto name (<date>-<source>-<title>)")
    pi.add_argument("--no-index", action="store_true", help="don't rebuild INDEX.md after import")
    pi.set_defaults(func=cmd_import)

    px = sub.add_parser("index", help="rebuild INDEX.md")
    common(px)
    px.set_defaults(func=cmd_index)

    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
