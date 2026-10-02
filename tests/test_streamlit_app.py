import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_app_renders_without_calling_gemini(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)

        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Choisis le type de sujet")
        self.assertEqual(app.selectbox[0].label, "Catégorie principale")
        self.assertIn("Impression", app.selectbox[0].options)
        self.assertEqual(app.selectbox[1].label, "Sous-catégorie")
        self.assertTrue(app.selectbox[1].disabled)
        self.assertEqual(app.selectbox[2].label, "Public visé")
        self.assertEqual(app.selectbox[2].value, "Grand public curieux")
        self.assertIn("Décideurs / porteurs de projet", app.selectbox[2].options)
        self.assertEqual(app.text_input[0].label, "Sujet ou angle précis")
        self.assertEqual(app.button[0].label, "Générer l’article")

    def test_subcategory_options_follow_the_selected_category(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)

        app.selectbox[0].select("Design").run()

        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[1].label, "Sous-catégorie")
        self.assertIn("Identité visuelle et branding", app.selectbox[1].options)
        self.assertIn("Autre design", app.selectbox[1].options)

    def test_audience_selection_is_independent_from_category(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=10)

        app.selectbox[2].select("Débutants").run()

        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[2].value, "Débutants")
        self.assertEqual(app.selectbox[0].value, "Choisis une catégorie")

    def test_session_history_restores_existing_outputs(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path))
        app.session_state["generation_history"] = [
            {
                "id": "saved-article",
                "topic": "pytest",
                "category": "IA",
                "subcategory": "Agents IA et automatisation",
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
        self.assertEqual(app.selectbox(key="history_selection").value, "saved-article")
        self.assertIn("Article sauvegardé", [item.value for item in app.markdown])
        self.assertEqual(app.download_button[0].label, "Télécharger l’article")

        app.button[1].click().run()

        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["generation_history"], [])