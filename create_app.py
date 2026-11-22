#!/usr/bin/env python3
"""Interactive App-Baukasten builder (Tkinter checkbox GUI + CLI fallback, zero external deps)."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys

TEMPLATE_DIR = Path(__file__).resolve().parent / "template"

KITS = [
    ("include_domain", "domain-django-kit (Stammdaten, Personen, Assets, Dokumente, Suche, Rechte-Matrix)", True),
    ("include_auth", "auth-django-kit (Login, Passwort, Benutzerprofil)", True),
    ("include_notify", "notify-django-kit (Benachrichtigungen, HTML-Mails, Webhooks)", True),
    ("include_cal", "cal-django-kit (Kalender-UI, .ics-Feed, CalDAV)", False),
    ("include_grid", "grid-django-kit (Tabellen, Suche, CSV/JSON-Export)", True),
    ("include_seed", "seed-django-kit (Demo-Seeding Framework)", True),
    ("include_ops", "ops-django-kit (Healthcheck /healthz, Audit-Log, Backup)", True),
]

IF_BLOCK_RE = re.compile(r"\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}", re.DOTALL)
VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


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

    github_repo = str(cfg.get("github_repo") or "").strip()
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
    port = str(cfg.get("port") or "8000").strip()
    if port != "8000":
        dc = dest / "docker-compose.yml"
        if dc.exists():
            _write_lf(dc, dc.read_text(encoding="utf-8").replace('"8000:8000"', f'"{port}:8000"'))

    if cfg.get("init_git", True):
        git_bin = shutil.which("git") or r"C:\Program Files\Git\cmd\git.exe"
        try:
            subprocess.run([git_bin, "init", "-b", "main"], cwd=dest, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    if cfg.get("build_pc_image", False):
        try:
            build_and_export_pc_image(dest, cfg["project_slug"])
        except Exception as exc:
            cfg["_image_build_error"] = str(exc)

    return dest


def _find_container_cli() -> tuple[str, str] | tuple[None, None]:
    """Return (binary_path, 'docker'|'podman') or (None, None)."""
    for name, win_paths in (
        ("docker", [r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"]),
        ("podman", [r"C:\Program Files\RedHat\Podman\podman.exe"]),
    ):
        found = shutil.which(name)
        if found:
            return found, name
        for wp in win_paths:
            if Path(wp).exists():
                return wp, name
    return None, None


def build_and_export_pc_image(dest: Path, project_slug: str) -> Path:
    cli_bin, cli_kind = _find_container_cli()
    if not cli_bin:
        raise RuntimeError(
            "Weder Docker Desktop (docker.exe) noch Podman (podman.exe) wurde auf diesem PC gefunden."
        )
    dist_dir = dest / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    image_tag = f"{project_slug}:latest"
    tar_path = dist_dir / f"{project_slug}-image.tar"
    if tar_path.exists():
        tar_path.unlink()

    build_proc = subprocess.run(
        [cli_bin, "build", "--platform", "linux/amd64", "-t", image_tag, "."],
        cwd=dest,
        capture_output=True,
        text=True,
    )
    if build_proc.returncode != 0:
        err = (build_proc.stderr or build_proc.stdout or "").strip()
        if cli_kind == "podman" and ("machine" in err.lower() or "connect" in err.lower() or "pipe" in err.lower()):
            raise RuntimeError(
                "Podman ist installiert, aber die Podman-VM läuft noch nicht.\n"
                "Bitte einmalig in PowerShell ausführen:\n"
                "  podman machine init --now\n"
                "(oder 'podman machine start') und danach .\\docker\\build-pc-image.ps1 starten."
            )
        raise RuntimeError(f"Container-Build ({cli_kind}) fehlgeschlagen:\n{err[:500]}")

    save_cmd = [cli_bin, "save", "-o", str(tar_path), image_tag]
    if cli_kind == "podman":
        save_cmd = [cli_bin, "save", "--format", "docker-archive", "-o", str(tar_path), image_tag]
    save_proc = subprocess.run(save_cmd, cwd=dest, capture_output=True, text=True)
    if save_proc.returncode != 0:
        err = (save_proc.stderr or save_proc.stdout or "").strip()
        raise RuntimeError(f"Image-Export ({cli_kind} save) fehlgeschlagen:\n{err[:500]}")
    return tar_path


def run_cli_wizard() -> dict:
    try:
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass
    print("=== Django NAS App-Baukasten ===")
    app_name = input("App-Name [Meine NAS App]: ").strip() or "Meine NAS App"
    default_slug = re.sub(r"[^a-z0-9]+", "_", app_name.lower()).strip("_") or "my_nas_app"
    raw_slug = input(f"Projekt-Slug [{default_slug}]: ").strip()
    project_slug = re.sub(r"[^a-z0-9_]+", "_", raw_slug.lower()).strip("_") or default_slug if raw_slug else default_slug
    default_dir = str(Path.cwd() / project_slug)
    target_dir = input(f"Zielordner [{default_dir}]: ").strip() or default_dir
    port = input("Port [8000]: ").strip() or "8000"
    allowed_hosts = input("ALLOWED_HOSTS [*]: ").strip() or "*"
    default_csrf = f"http://localhost:{port}"
    csrf_origins = input(f"CSRF_TRUSTED_ORIGINS [{default_csrf}]: ").strip() or default_csrf
    github_repo = input("GitHub-Repo für In-App Updates (optional, z.B. bzaiser/meine-app) []: ").strip()
    debug = input("DJANGO_DEBUG? (j/N) [N]: ").strip().lower() in ("j", "y", "ja", "yes")
    build_pc_image = input("Docker-Image jetzt am PC bauen & als .tar für NAS exportieren? (j/N) [N]: ").strip().lower() in ("j", "y", "ja", "yes")

    cfg = {
        "app_name": app_name,
        "project_slug": project_slug,
        "target_dir": target_dir,
        "port": port,
        "allowed_hosts": allowed_hosts,
        "csrf_origins": csrf_origins,
        "github_repo": github_repo,
        "debug": debug,
        "build_pc_image": build_pc_image,
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

    result = {}
    root = tk.Tk()
    root.title("Django NAS App-Baukasten")
    root.geometry("600x630")
    root.resizable(False, False)

    frm = ttk.Frame(root, padding=16)
    frm.pack(fill="both", expand=True)

    app_name_var = tk.StringVar(value="Meine NAS App")
    slug_var = tk.StringVar(value="meine_nas_app")
    dir_var = tk.StringVar(value=str(Path(__file__).resolve().parent.parent / "meine_nas_app"))
    port_var = tk.StringVar(value="8000")
    hosts_var = tk.StringVar(value="*")
    csrf_var = tk.StringVar(value="http://localhost:8000")
    repo_var = tk.StringVar(value="")
    debug_var = tk.BooleanVar(value=False)
    git_var = tk.BooleanVar(value=True)
    build_img_var = tk.BooleanVar(value=False)

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
    add_row(3, "Docker-Port:", port_var)
    add_row(4, "ALLOWED_HOSTS:", hosts_var)
    add_row(5, "CSRF_TRUSTED_ORIGINS:", csrf_var)
    add_row(6, "GitHub-Repo (optional):", repo_var)

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
    ttk.Checkbutton(frm, text="Git-Repository direkt initialisieren", variable=git_var).grid(row=r, column=0, columnspan=3, sticky="w")
    r += 1
    ttk.Checkbutton(frm, text="Docker-Image direkt am PC bauen & als .tar für NAS exportieren", variable=build_img_var).grid(row=r, column=0, columnspan=3, sticky="w")
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
            "build_pc_image": build_img_var.get(),
            "secret_key": secrets.token_urlsafe(48),
        })
        for k, v in kit_vars.items():
            result[k] = v.get()
        try:
            dest = generate_app(result)
            msg = f"App erstellt unter:\n{dest}\n\n"
            if result.get("_image_build_error"):
                messagebox.showwarning(
                    "App erstellt (Image-Build Hinweis)",
                    msg + f"Die App-Dateien sind komplett fertig, aber der PC-Image-Build konnte noch nicht ausgeführt werden:\n\n{result['_image_build_error']}",
                )
            elif result["build_pc_image"]:
                msg += f"PC-Image exportiert nach:\n{dest / 'dist' / (result['project_slug'] + '-image.tar')}\n\nAuf dem NAS starten mit:\n./docker/load-nas-image.sh"
                messagebox.showinfo("Fertig", msg)
            else:
                msg += "Am PC Image für NAS bauen:\n.\\docker\\build-pc-image.ps1\n\nAuf dem NAS starten:\n./docker/load-nas-image.sh (oder ./docker/update-fast.sh)"
                messagebox.showinfo("Fertig", msg)
            root.destroy()
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc))

    ttk.Button(frm, text="App & .env erstellen", command=on_create).grid(row=r, column=1, sticky="e", pady=14)
    root.mainloop()
    return result or None


def main():
    parser = argparse.ArgumentParser(description="Erstellt eine neue Django-NAS-App inkl. .env.")
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
    print("Starten mit: docker compose up --build")


if __name__ == "__main__":
    main()
