#!/usr/bin/env python3
"""Interactive App-Baukasten builder (Tkinter checkbox GUI + CLI fallback, zero external deps)."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

TEMPLATE_DIR = Path(__file__).resolve().parent / "template"

KITS = [
    ("include_domain", "domain-django-kit (Stammdaten, Personen, Assets, Dokumente, Suche, Rechte-Matrix)", True),
    ("include_auth", "auth-django-kit (Login, Passwort, Benutzerprofil)", True),
    ("include_notify", "notify-django-kit (Benachrichtigungen, HTML-Mails, Webhooks)", True),
    ("include_cal", "cal-django-kit (Kalender-UI, .ics-Feed, CalDAV)", False),
    ("include_grid", "grid-django-kit (Tabellen, Suche, CSV/JSON-Export)", True),
    ("include_seed", "seed-django-kit (Demo-Seeding Framework)", True),
    ("include_ops", "ops-django-kit (Healthcheck /healthz, Audit-Log, Backup, In-App Updates)", True),
]

IF_BLOCK_RE = re.compile(r"\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}", re.DOTALL)
VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _get_git_bin() -> str:
    return shutil.which("git") or r"C:\Program Files\Git\cmd\git.exe"


def _detect_github_owner() -> str:
    git_bin = _get_git_bin()
    try:
        proc = subprocess.run([git_bin, "config", "--global", "user.name"], capture_output=True, text=True, timeout=3)
        name = (proc.stdout or "").strip()
        if name and " " not in name:
            return name
    except Exception:
        pass
    return "bzaiser"


def _get_github_token_from_git() -> str:
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("OPS_GITHUB_TOKEN") or "").strip()
    if token:
        return token
    git_bin = _get_git_bin()
    try:
        proc = subprocess.run(
            [git_bin, "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in (proc.stdout or "").splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def _ensure_github_repo_exists(github_repo: str, private: bool = False) -> tuple[bool, str]:
    """Ensure owner/repo exists on GitHub (creating it via REST API if missing)."""
    if "/" not in github_repo:
        return False, f"Ungültiges Repo-Format '{github_repo}' (erwartet: owner/repo)."
    owner, repo_name = [p.strip() for p in github_repo.split("/", 1)]
    token = _get_github_token_from_git()
    if not token:
        return False, "Kein GitHub-Token im Git Credential Manager gefunden."

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "starter-django-nas-generator/1.0",
        "Content-Type": "application/json",
    }

    # 1. Check if repo already exists
    check_req = urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo_name}", headers=headers)
    try:
        with urllib.request.urlopen(check_req, timeout=8) as resp:
            if resp.status == 200:
                return True, f"GitHub-Repo {owner}/{repo_name} existiert bereits."
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return False, f"GitHub-API Fehler ({e.code}) beim Prüfen von {owner}/{repo_name}."
    except Exception as exc:
        return False, f"GitHub-Verbindungsfehler: {exc}"

    # 2. Create repo under authenticated user
    payload = json.dumps({"name": repo_name, "private": bool(private), "auto_init": False}).encode("utf-8")
    create_req = urllib.request.Request(
        "https://api.github.com/user/repos",
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(create_req, timeout=10) as resp:
            if resp.status in (200, 201):
                return True, f"GitHub-Repo {owner}/{repo_name} neu angelegt."
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        return False, f"GitHub-Repo konnte nicht erstellt werden (HTTP {e.code}): {body}"
    except Exception as exc:
        return False, f"GitHub-Repo Erstellung fehlgeschlagen: {exc}"
    return False, "Unbekannter Fehler bei GitHub-Repo-Erstellung."


def init_commit_and_push_git(dest: Path, cfg: dict) -> list[str]:
    """Initialize git repo, commit all generated files with LF/+x, and optionally push to GitHub."""
    notes: list[str] = []
    git_bin = _get_git_bin()
    try:
        subprocess.run([git_bin, "init", "-b", "main"], cwd=dest, check=True, capture_output=True, text=True)
        subprocess.run([git_bin, "config", "core.autocrlf", "false"], cwd=dest, check=False, capture_output=True)
        subprocess.run([git_bin, "add", "-A"], cwd=dest, check=True, capture_output=True, text=True)
        sh_files = ["entrypoint.sh"] + [
            f"docker/{p.name}" for p in (dest / "docker").glob("*.sh")
        ] if (dest / "docker").exists() else ["entrypoint.sh"]
        subprocess.run(
            [git_bin, "update-index", "--chmod=+x", *sh_files],
            cwd=dest,
            check=False,
            capture_output=True,
        )
        cproc = subprocess.run(
            [git_bin, "commit", "-m", "chore: initial app created with starter-django-nas"],
            cwd=dest,
            capture_output=True,
            text=True,
        )
        if cproc.returncode == 0:
            notes.append("Lokaler Git-Commit auf Branch 'main' erstellt.")
    except Exception as exc:
        notes.append(f"Git-Init/Commit Hinweis: {exc}")
        return notes

    github_repo = str(cfg.get("github_repo") or "").strip().strip("/")
    if github_repo and "/" not in github_repo:
        github_repo = f"{_detect_github_owner()}/{github_repo}"
        cfg["github_repo"] = github_repo

    if not github_repo:
        return notes

    remote_url = f"https://github.com/{github_repo}.git"
    subprocess.run([git_bin, "remote", "remove", "origin"], cwd=dest, check=False, capture_output=True)
    subprocess.run([git_bin, "remote", "add", "origin", remote_url], cwd=dest, check=False, capture_output=True)
    notes.append(f"Git-Remote 'origin' gesetzt auf {remote_url}")

    if cfg.get("push_github", True):
        ok, msg = _ensure_github_repo_exists(github_repo, private=bool(cfg.get("github_private", False)))
        notes.append(msg)
        if ok:
            pproc = subprocess.run(
                [git_bin, "push", "-u", "origin", "main"],
                cwd=dest,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if pproc.returncode == 0:
                notes.append(f"Erfolgreich nach https://github.com/{github_repo} gepusht!")
            else:
                err = (pproc.stderr or pproc.stdout or "").strip()
                cfg["_git_push_error"] = f"git push fehlgeschlagen:\n{err[:300]}"
                notes.append(cfg["_git_push_error"])
        else:
            cfg["_git_push_error"] = msg
    return notes


def render_template_text(text: str, ctx: dict) -> str:
    def _eval_if(match):
        key, body = match.group(1), match.group(2)
        return body if ctx.get(key) else ""

    prev = None
    while prev != text:
        prev = text
        text = IF_BLOCK_RE.sub(_eval_if, text)
    return VAR_RE.sub(lambda m: str(ctx.get(m.group(1), "")), text)


def _write_lf(path: Path, text: str):
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def generate_app(cfg: dict) -> Path:
    port_str = str(cfg.get("port") or "8000").strip()
    if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
        raise ValueError(f"Ungültiger TCP-Port '{port_str}' (erlaubt: 1 bis 65535, z. B. 8020).")

    github_repo = str(cfg.get("github_repo") or "").strip().strip("/")
    if github_repo and "/" not in github_repo:
        github_repo = f"{_detect_github_owner()}/{github_repo}"
    cfg["github_repo"] = github_repo

    dest = Path(cfg["target_dir"]).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    for src in TEMPLATE_DIR.rglob("*"):
        rel = src.relative_to(TEMPLATE_DIR)
        if src.is_dir():
            (dest / rel).mkdir(parents=True, exist_ok=True)
            continue
        out_rel = rel.with_name(rel.name[:-6]) if rel.name.endswith(".jinja") else rel
        out_path = dest / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if rel.name.endswith(".jinja"):
            rendered = render_template_text(src.read_text(encoding="utf-8"), cfg)
            _write_lf(out_path, rendered)
            if out_path.suffix == ".sh":
                try:
                    os.chmod(out_path, 0o755)
                except OSError:
                    pass
        else:
            shutil.copy2(src, out_path)
            if out_path.suffix == ".sh":
                _write_lf(out_path, out_path.read_text(encoding="utf-8"))
                try:
                    os.chmod(out_path, 0o755)
                except OSError:
                    pass

    env_content = (
        f"DJANGO_SECRET_KEY={cfg['secret_key']}\n"
        f"DJANGO_DEBUG={'True' if cfg['debug'] else 'False'}\n"
        f"DJANGO_ALLOWED_HOSTS={cfg['allowed_hosts']}\n"
        f"CSRF_TRUSTED_ORIGINS={cfg['csrf_origins']}\n"
        f"DESIGN_STUDIO_APP_NAME={cfg['app_name']}\n"
        f"OPS_GITHUB_REPO={github_repo}\n"
    )
    _write_lf(dest / ".env", env_content)

    # Adjust port in docker-compose.yml if non-default
    if port_str != "8000":
        dc = dest / "docker-compose.yml"
        if dc.exists():
            _write_lf(dc, dc.read_text(encoding="utf-8").replace('"8000:8000"', f'"{port_str}:8000"'))

    if cfg.get("init_git", True):
        cfg["_git_notes"] = init_commit_and_push_git(dest, cfg)

    return dest


def run_cli_wizard() -> dict:
    try:
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass
    print("=== Django NAS App-Baukasten ===")
    owner = _detect_github_owner()
    app_name = input("App-Name [Meine NAS App]: ").strip() or "Meine NAS App"
    default_slug = re.sub(r"[^a-z0-9]+", "_", app_name.lower()).strip("_") or "my_nas_app"
    raw_slug = input(f"Projekt-Slug [{default_slug}]: ").strip()
    project_slug = re.sub(r"[^a-z0-9_]+", "_", raw_slug.lower()).strip("_") or default_slug if raw_slug else default_slug
    default_dir = str(Path.cwd() / project_slug)
    target_dir = input(f"Zielordner [{default_dir}]: ").strip() or default_dir
    port = input("Port (1-65535) [8000]: ").strip() or "8000"
    allowed_hosts = input("ALLOWED_HOSTS [*]: ").strip() or "*"
    default_csrf = f"http://localhost:{port}"
    csrf_origins = input(f"CSRF_TRUSTED_ORIGINS [{default_csrf}]: ").strip() or default_csrf
    default_repo = f"{owner}/{project_slug}"
    github_repo = input(f"GitHub-Repo [{default_repo}]: ").strip() or default_repo
    push_ans = input("GitHub-Repo automatisch anlegen, committen & pushen? (J/n) [J]: ").strip().lower()
    push_github = True if not push_ans else push_ans in ("j", "y", "ja", "yes")
    debug = input("DJANGO_DEBUG? (j/N) [N]: ").strip().lower() in ("j", "y", "ja", "yes")

    cfg = {
        "app_name": app_name,
        "project_slug": project_slug,
        "target_dir": target_dir,
        "port": port,
        "allowed_hosts": allowed_hosts,
        "csrf_origins": csrf_origins,
        "github_repo": github_repo,
        "push_github": push_github,
        "github_private": False,
        "debug": debug,
        "secret_key": secrets.token_urlsafe(48),
        "init_git": True,
    }
    print("\nBaukasten-Module auswählen (J/n):")
    for key, label, default in KITS:
        hint = "J/n" if default else "j/N"
        ans = input(f"  [{hint}] {label}: ").strip().lower()
        cfg[key] = default if not ans else ans in ("j", "y", "ja", "yes")
    return cfg


def run_gui_wizard() -> dict | None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    owner = _detect_github_owner()
    base_parent = Path(__file__).resolve().parent.parent
    result = {}
    root = tk.Tk()
    root.title("Django NAS App-Baukasten")
    root.geometry("620x640")
    root.resizable(False, False)

    frm = ttk.Frame(root, padding=16)
    frm.pack(fill="both", expand=True)

    app_name_var = tk.StringVar(value="Meine NAS App")
    slug_var = tk.StringVar(value="meine_nas_app")
    dir_var = tk.StringVar(value=str(base_parent / "meine_nas_app"))
    port_var = tk.StringVar(value="8020")
    hosts_var = tk.StringVar(value="*")
    csrf_var = tk.StringVar(value="http://localhost:8020")
    repo_var = tk.StringVar(value=f"{owner}/meine_nas_app")
    debug_var = tk.BooleanVar(value=False)
    git_var = tk.BooleanVar(value=True)
    push_var = tk.BooleanVar(value=True)
    priv_var = tk.BooleanVar(value=False)

    # Auto-sync slug, target_dir and github_repo when app_name or slug changes
    _syncing = {"busy": False}

    def _on_app_name_change(*_):
        if _syncing["busy"]:
            return
        _syncing["busy"] = True
        try:
            s = re.sub(r"[^a-z0-9]+", "_", app_name_var.get().lower()).strip("_") or "meine_nas_app"
            slug_var.set(s)
            dir_var.set(str(base_parent / s))
            repo_var.set(f"{owner}/{s}")
        finally:
            _syncing["busy"] = False

    def _on_slug_change(*_):
        if _syncing["busy"]:
            return
        _syncing["busy"] = True
        try:
            s = re.sub(r"[^a-z0-9_]+", "_", slug_var.get().lower()).strip("_")
            if s:
                dir_var.set(str(base_parent / s))
                repo_var.set(f"{owner}/{s}")
        finally:
            _syncing["busy"] = False

    def _on_port_change(*_):
        p = port_var.get().strip()
        if p.isdigit():
            csrf_var.set(f"http://localhost:{p}")

    app_name_var.trace_add("write", _on_app_name_change)
    slug_var.trace_add("write", _on_slug_change)
    port_var.trace_add("write", _on_port_change)

    def add_row(row, label, var, browse=False):
        ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ent = ttk.Entry(frm, textvariable=var, width=42)
        ent.grid(row=row, column=1, sticky="ew", pady=3, padx=(8, 0))
        if browse:
            def _pick():
                d = filedialog.askdirectory()
                if d:
                    var.set(d)
            ttk.Button(frm, text="...", width=3, command=_pick).grid(row=row, column=2, padx=(4, 0))

    add_row(0, "App-Name:", app_name_var)
    add_row(1, "Projekt-Slug:", slug_var)
    add_row(2, "Zielordner:", dir_var, browse=True)
    add_row(3, "Docker-Port (1-65535):", port_var)
    add_row(4, "ALLOWED_HOSTS:", hosts_var)
    add_row(5, "CSRF_TRUSTED_ORIGINS:", csrf_var)
    add_row(6, "GitHub-Repo:", repo_var)

    ttk.Separator(frm).grid(row=7, column=0, columnspan=3, sticky="ew", pady=10)
    ttk.Label(frm, text="Module zum Anhaken:", font=("Segoe UI", 10, "bold")).grid(row=8, column=0, columnspan=3, sticky="w")

    kit_vars = {}
    r = 9
    for key, label, default in KITS:
        v = tk.BooleanVar(value=default)
        kit_vars[key] = v
        ttk.Checkbutton(frm, text=label, variable=v).grid(row=r, column=0, columnspan=3, sticky="w", pady=2)
        r += 1

    ttk.Separator(frm).grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
    r += 1
    ttk.Checkbutton(frm, text="DJANGO_DEBUG=True (nur Entwicklung)", variable=debug_var).grid(row=r, column=0, columnspan=3, sticky="w")
    r += 1
    ttk.Checkbutton(frm, text="Git-Repository initialisieren & Initial-Commit erstellen", variable=git_var).grid(row=r, column=0, columnspan=3, sticky="w")
    r += 1
    ttk.Checkbutton(frm, text="GitHub-Repository automatisch auf GitHub anlegen & direkt pushen", variable=push_var).grid(row=r, column=0, columnspan=3, sticky="w")
    r += 1
    ttk.Checkbutton(frm, text="GitHub-Repository als 'Private' anlegen (Standard: Public für NAS git clone)", variable=priv_var).grid(row=r, column=0, columnspan=3, sticky="w")
    r += 1

    def on_create():
        result.update({
            "app_name": app_name_var.get().strip() or "Meine NAS App",
            "project_slug": slug_var.get().strip() or "my_nas_app",
            "target_dir": dir_var.get().strip(),
            "port": port_var.get().strip() or "8000",
            "allowed_hosts": hosts_var.get().strip() or "*",
            "csrf_origins": csrf_var.get().strip() or "http://localhost:8000",
            "github_repo": repo_var.get().strip(),
            "debug": debug_var.get(),
            "init_git": git_var.get(),
            "push_github": push_var.get(),
            "github_private": priv_var.get(),
            "secret_key": secrets.token_urlsafe(48),
        })
        for k, v in kit_vars.items():
            result[k] = v.get()
        try:
            dest = generate_app(result)
            notes_str = "\n".join(f"• {n}" for n in (result.get("_git_notes") or []))
            gh = result.get("github_repo")
            slug = result["project_slug"]
            nas_cmd = (
                f"git clone https://github.com/{gh}.git && cd {slug} && ./docker/update-fast.sh"
                if gh and not result.get("_git_push_error")
                else "./docker/update-fast.sh"
            )
            msg = f"App erstellt unter:\n{dest}\n\n{notes_str}\n\nAuf dem NAS starten (0,1 Sek., kein Build!):\n{nas_cmd}"
            if result.get("_git_push_error"):
                messagebox.showwarning("App erstellt (GitHub-Push Hinweis)", msg)
            else:
                messagebox.showinfo("Fertig", msg)
            root.destroy()
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))

    ttk.Button(frm, text="App erstellen & nach GitHub pushen", command=on_create).grid(row=r, column=1, sticky="e", pady=14)
    root.mainloop()
    return result or None


def main():
    parser = argparse.ArgumentParser(description="Erstellt eine neue Django-NAS-App inkl. .env & GitHub-Push.")
    parser.add_argument("--cli", action="store_true", help="Terminal-Modus statt GUI verwenden.")
    args = parser.parse_args()

    if not args.cli:
        try:
            run_gui_wizard()
            return
        except Exception:
            pass

    cfg = run_cli_wizard()
    dest = generate_app(cfg)
    print(f"\nFertig! App erstellt unter: {dest}")
    for n in cfg.get("_git_notes") or []:
        print(f"  - {n}")


if __name__ == "__main__":
    main()
