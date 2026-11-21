from pathlib import Path
import sys
import tempfile
import unittest

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from create_app import generate_app


class CreateAppTests(unittest.TestCase):
    def test_generate_app_renders_env_settings_and_selected_kits(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "demo_nas_app"
            dest = generate_app({
                "app_name": "Demo NAS",
                "project_slug": "demo_nas",
                "target_dir": str(target),
                "port": "8090",
                "allowed_hosts": "nas.local",
                "csrf_origins": "http://nas.local:8090",
                "debug": False,
                "secret_key": "test-secret-xyz",
                "init_git": False,
                "include_auth": True,
                "include_notify": False,
                "include_cal": True,
                "include_grid": True,
                "include_seed": False,
                "include_ops": True,
            })

            env_text = (dest / ".env").read_text(encoding="utf-8")
            self.assertIn("DESIGN_STUDIO_APP_NAME=Demo NAS", env_text)
            self.assertIn("DJANGO_SECRET_KEY=test-secret-xyz", env_text)
            self.assertIn("DJANGO_ALLOWED_HOSTS=nas.local", env_text)

            dc_text = (dest / "docker-compose.yml").read_text(encoding="utf-8")
            self.assertIn('"8090:8000"', dc_text)
            self.assertIn("container_name: demo_nas", dc_text)
            self.assertIn("ds_pkg:/opt/ds-pkg", dc_text)
            self.assertIn(".:/app", dc_text)
            self.assertIn("./data:/app/data", dc_text)

            req_text = (dest / "requirements.txt").read_text(encoding="utf-8")
            self.assertIn("auth-django-kit", req_text)
            self.assertIn("cal-django-kit", req_text)
            self.assertNotIn("notify-django-kit", req_text)
            self.assertNotIn("seed-django-kit", req_text)

            settings_text = (dest / "config" / "settings.py").read_text(encoding="utf-8")
            self.assertIn("apply_runtime_installed_apps", settings_text)

            urls_text = (dest / "config" / "urls.py").read_text(encoding="utf-8")
            self.assertIn("cal_kit.urls", urls_text)
            self.assertIn("get_runtime_urlpatterns", urls_text)
            self.assertNotIn("notify_kit.urls", urls_text)

            uf_text = (dest / "docker" / "update-fast.sh").read_text(encoding="utf-8")
            self.assertIn("ops_sync_kits", uf_text)
            self.assertTrue((dest / "docker" / "update.sh").exists())

            skill_text = (dest / ".agents" / "skills" / "django-baukasten" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("VERBOT nicht-persistenter Terminal-Fixes", skill_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
