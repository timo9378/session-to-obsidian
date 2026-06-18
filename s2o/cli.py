"""s2o CLI:把一場 Claude Code / Copilot session 匯入 Obsidian。

  s2o import <file> --vault <vault根> [--cluster claude_cli|time] [--images] ...
  s2o index --vault <vault根>
"""
from __future__ import annotations
import argparse
import glob
import os
import shutil
import sys

from . import adapters, cluster as clustermod, index as indexmod, parse, render
from .slugs import session_slug


def _paths(vault, subdir, attachments, slug):
    out_dir = os.path.join(vault, subdir, slug)
    attach_rel = attachments
    attach_abs = os.path.join(vault, attachments, slug)
    return out_dir, attach_abs, attach_rel


def _read_origin(md_path) -> str | None:
    """讀 .md frontmatter 的 originSessionId(只看開頭 --- 區塊)。"""
    try:
        with open(md_path, encoding="utf-8") as f:
            if f.readline().strip() != "---":
                return None
            for _ in range(20):
                ln = f.readline()
                if not ln or ln.strip() == "---":
                    break
                if ln.startswith("originSessionId:"):
                    return ln.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


def _dedupe(sessions_dir, vault, attachments, origin_id) -> list[str]:
    """匯入前先刪同源舊資料夾(免標題變動產生重複)。回傳被刪的 slug。"""
    if not origin_id:
        return []
    removed = []
    for md in glob.glob(os.path.join(sessions_dir, "*", "*.md")):
        if _read_origin(md) != origin_id:
            continue
        folder = os.path.dirname(md)
        slug = os.path.basename(folder)
        shutil.rmtree(folder, ignore_errors=True)
        shutil.rmtree(os.path.join(vault, attachments, slug), ignore_errors=True)
        removed.append(slug)
    return removed


def cmd_import(a) -> int:
    records, meta = adapters.load(a.file, a.source)
    steps = parse.parse_records(records, with_images=a.images)
    if not steps:
        print("沒有可匯入的步驟(空 session?)", file=sys.stderr)
        return 1

    backend = a.cluster
    try:
        clustering = clustermod.cluster(steps, backend=backend, model=a.model, timeout=a.timeout)
    except clustermod.ClusterError as e:
        if backend == "claude_cli" and not a.no_fallback:
            print(f"⚠ 分群({backend})失敗:{e}\n  → 退回時間分段(--cluster time)", file=sys.stderr)
            clustering = clustermod.cluster(steps, backend="time")
        else:
            print(f"分群失敗:{e}", file=sys.stderr)
            return 2

    title = clustering["title"]
    source = meta.get("source", "session")
    origin_id = os.path.splitext(os.path.basename(a.file))[0]
    slug = a.slug or session_slug(meta.get("date", ""), source, title)
    sessions_dir = os.path.join(a.vault, a.subdir)
    removed = _dedupe(sessions_dir, a.vault, a.attachments, origin_id)

    out_dir, attach_abs, attach_rel = _paths(a.vault, a.subdir, a.attachments, slug)
    stats = render.render(steps, clustering, out_dir, slug, attach_abs, attach_rel,
                          noimg=not a.images, origin_id=origin_id, source=source)
    if removed:
        print(f"  (取代同源舊版:{', '.join(removed)})")
    print(f"✓ {slug}")
    print(f"  {stats['steps']} 步 · {stats['topics']} 主題 · {stats['images']} 圖 · 後端={backend} · {title}")

    if not a.no_index:
        ix = indexmod.build_index(os.path.join(a.vault, a.subdir))
        print(f"  INDEX.md 更新:{ix['sessions']} 場 · {ix['topics']} 主題")
    return 0


def cmd_index(a) -> int:
    ix = indexmod.build_index(os.path.join(a.vault, a.subdir))
    print(f"✓ INDEX.md:{ix['sessions']} 場 · {ix['topics']} 主題")
    return 0


def main(argv=None) -> int:
    env_vault = os.environ.get("S2O_VAULT")
    p = argparse.ArgumentParser(prog="s2o", description="Claude Code / Copilot session → Obsidian 主題回顧")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--vault", default=env_vault, required=env_vault is None,
                        help="Obsidian vault 根目錄(或設環境變數 S2O_VAULT)")
        sp.add_argument("--subdir", default="90-Meta/sessions", help="session 放哪(vault 相對)")

    pi = sub.add_parser("import", help="匯入一場 session")
    pi.add_argument("file", help="session jsonl(Claude 原生 或 Copilot append-log)")
    common(pi)
    pi.add_argument("--source", default="auto", choices=["auto", "claude", "copilot"])
    pi.add_argument("--cluster", default="claude_cli", choices=["claude_cli", "time"],
                    help="分群後端(claude_cli=host Claude headless;time=純時間分段降級)")
    pi.add_argument("--model", default=None, help="claude_cli 後端用的模型(預設用 CC 設定)")
    pi.add_argument("--timeout", type=int, default=180, help="claude_cli 逾時秒數")
    pi.add_argument("--no-fallback", action="store_true", help="claude_cli 失敗時不退回 time")
    pi.add_argument("--attachments", default="_attachments/sessions", help="截圖放哪(vault 相對,gitignore)")
    pi.add_argument("--images", action="store_true", help="抽出截圖(預設純文字 = 不抽圖)")
    pi.add_argument("--slug", default=None, help="覆蓋自動命名(<date>-<source>-<標題>)")
    pi.add_argument("--no-index", action="store_true", help="匯入後不更新 INDEX.md")
    pi.set_defaults(func=cmd_import)

    px = sub.add_parser("index", help="重建 INDEX.md")
    common(px)
    px.set_defaults(func=cmd_index)

    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
