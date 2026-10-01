import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_app_renders_without_calling_gemini(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Atelier d’articles techniques")
        self.assertEqual(app.text_input[0].label, "Sujet technique")
        self.assertEqual(app.button[0].label, "Générer l’article")

    def test_session_history_restores_existing_outputs(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path))
        app.session_state["generation_history"] = [
            {
                "id": "saved-article",
                "topic": "pytest",
                "created_at": "2026-10-01 12:00",
                "outputs": {
                    "blog_outline": "Plan sauvegardé",
                    "blog_post": "Article sauvegardé",
                    "quality_review": "PASS",
                },
            }
        ]

        app.run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, "saved-article")
        self.assertIn("Article sauvegardé", [item.value for item in app.markdown])
        self.assertEqual(app.download_button[0].label, "Télécharger l’article")

        app.button[1].click().run()

        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["generation_history"], [])