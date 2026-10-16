import io
import json
import ssl
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from blog_agent.media import (
    build_search_links,
    collect_article_media,
    parse_article_sections,
    search_commons_media,
)
from streamlit.testing.v1 import AppTest


class CommonsMediaTests(unittest.TestCase):
    @patch("blog_agent.media.urlopen")
    def test_image_search_returns_commons_thumbnail_and_source(self, mock_urlopen):
        payload = {
            "query": {
                "pages": {
                    "1": {
                        "index": 1,
                        "title": "File:Example.jpg",
                        "imageinfo": [
                            {
                                "mediatype": "BITMAP",
                                "mime": "image/jpeg",
                                "url": "https://upload.wikimedia.org/example.jpg",
                                "thumburl": "https://thumb.wikimedia.org/example.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example.jpg",
                            }
                        ],
                    }
                }
            }
        }
        mock_urlopen.return_value = io.BytesIO(json.dumps(payload).encode())

        result = search_commons_media("architecture", "image")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Example.jpg")
        self.assertEqual(
            result[0]["thumbnail_url"],
            "https://thumb.wikimedia.org/example.jpg",
        )
        self.assertIsInstance(
            mock_urlopen.call_args.kwargs["context"], ssl.SSLContext
        )

    @patch("blog_agent.media.urlopen")
    def test_video_search_ignores_non_browser_playable_formats(self, mock_urlopen):
        payload = {
            "query": {
                "pages": {
                    "1": {
                        "index": 1,
                        "title": "File:Example.ogv",
                        "imageinfo": [
                            {
                                "mediatype": "VIDEO",
                                "mime": "application/ogg",
                                "url": "https://upload.wikimedia.org/example.ogv",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example.ogv",
                            }
                        ],
                    },
                    "2": {
                        "index": 2,
                        "title": "File:Example.webm",
                        "imageinfo": [
                            {
                                "mediatype": "VIDEO",
                                "mime": "video/webm",
                                "url": "https://upload.wikimedia.org/example.webm",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example.webm",
                            }
                        ],
                    },
                }
            }
        }
        mock_urlopen.return_value = io.BytesIO(json.dumps(payload).encode())

        result = search_commons_media("architecture", "video")

        self.assertEqual([item["title"] for item in result], ["Example.webm"])


class ArticleMediaTests(unittest.TestCase):
    def test_parse_article_sections_keeps_intro_and_h2_headings(self):
        article = (
            "# Titre\n"
            "Phrase d’introduction.\n"
            "## Choisir le papier\n"
            "Le grammage décide de la tenue.\n"
            "### Sous-titre\n"
            "Premier paragraphe de la section.\n"
            "## Finition\n"
            "- un item\n"
            "```python\nprint(\"ignoré\")\n```\n"
            "Conclusion finale.\n"
        )

        sections = parse_article_sections(article)

        self.assertEqual(
            [section["heading"] for section in sections],
            ["Introduction", "Choisir le papier", "Finition"],
        )
        self.assertEqual(sections[0]["paragraph"], "Phrase d’introduction.")
        self.assertEqual(sections[1]["paragraph"], "Le grammage décide de la tenue.")
        self.assertEqual(sections[2]["paragraph"], "Conclusion finale.")

    def test_build_search_links_encodes_the_query(self):
        links = build_search_links("papier grammage")

        self.assertEqual(
            links["youtube"],
            "https://www.youtube.com/results?search_query=papier+grammage",
        )
        self.assertIn("tbm=isch", links["google_images"])
        self.assertIn("q=papier+grammage", links["google_images"])
        self.assertIn("search=papier+grammage", links["commons"])
        self.assertIn("type=image", links["commons"])

    @patch("blog_agent.media.search_commons_media")
    def test_collect_article_media_adds_images_links_and_errors(self, mock_search):
        def fake_search(query, media_type):
            self.assertEqual(media_type, "image")
            if "Finition" in query:
                raise URLError("hors ligne")
            return [
                {
                    "title": f"Image {index}.jpg",
                    "url": f"https://upload.wikimedia.org/{index}.jpg",
                    "thumbnail_url": f"https://thumb.wikimedia.org/{index}.jpg",
                    "description_url": (
                        f"https://commons.wikimedia.org/wiki/File:{index}.jpg"
                    ),
                    "mime": "image/jpeg",
                }
                for index in range(4)
            ]

        mock_search.side_effect = fake_search

        article = (
            "Intro.\n"
            "## Choisir\n"
            "Texte utile.\n"
            "## Finition\n"
            "Autre texte.\n"
        )

        sections = collect_article_media(article, "papier")

        self.assertEqual(len(sections), 3)
        self.assertEqual(sections[0]["query"], "papier")
        self.assertEqual(sections[1]["query"], "papier Choisir")
        self.assertEqual(sections[1]["paragraph"], "Texte utile.")
        self.assertEqual(len(sections[1]["images"]), 3)
        self.assertIn("papier+Choisir", sections[1]["links"]["youtube"])
        self.assertIsNone(sections[1]["error"])
        self.assertEqual(sections[2]["images"], [])
        self.assertIsNotNone(sections[2]["error"])
        self.assertTrue(sections[2]["links"]["youtube"].startswith("https://"))

    def test_collect_article_media_returns_nothing_for_empty_article(self):
        self.assertEqual(collect_article_media("", "sujet"), [])


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

        app.button[
            next(
                index
                for index, button in enumerate(app.button)
                if button.label == "Effacer l’historique"
            )
        ].click().run()

        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["generation_history"], [])

    @staticmethod
    def _saved_entry(**overrides):
        entry = {
            "id": "saved-article",
            "topic": "pytest",
            "category": "IA",
            "subcategory": "Agents IA et automatisation",
            "created_at": "2026-10-01 12:00",
            "outputs": {
                "blog_outline": "Plan sauvegardé",
                "blog_post": (
                    "Introduction de l’article.\n"
                    "## Configuration\n"
                    "Le premier paragraphe.\n"
                ),
                "quality_review": "PASS",
            },
        }
        entry.update(overrides)
        return entry

    def test_media_tab_renders_sections_images_and_search_links(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path))
        app.session_state["generation_history"] = [
            self._saved_entry(
                media=[
                    {
                        "heading": "Configuration",
                        "query": "pytest Configuration",
                        "paragraph": "Le premier paragraphe.",
                        "images": [
                            {
                                "title": "Example.jpg",
                                "url": "https://upload.wikimedia.org/example.jpg",
                                "thumbnail_url": (
                                    "https://thumb.wikimedia.org/example.jpg"
                                ),
                                "description_url": (
                                    "https://commons.wikimedia.org/wiki/File:Example.jpg"
                                ),
                                "mime": "image/jpeg",
                            }
                        ],
                        "links": build_search_links("pytest Configuration"),
                        "error": None,
                    }
                ]
            )
        ]

        app.run(timeout=10)

        self.assertFalse(app.exception)
        markdown_values = [item.value for item in app.markdown]
        self.assertTrue(
            any(
                "▶ Vidéos YouTube" in value and "Images Commons" in value
                for value in markdown_values
            ),
            markdown_values,
        )

    def test_media_tab_collects_media_for_saved_article(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path))
        app.session_state["generation_history"] = [self._saved_entry()]

        with patch("blog_agent.media.search_commons_media") as mock_search:
            mock_search.return_value = [
                {
                    "title": "Example.jpg",
                    "url": "https://upload.wikimedia.org/example.jpg",
                    "thumbnail_url": "https://thumb.wikimedia.org/example.jpg",
                    "description_url": (
                        "https://commons.wikimedia.org/wiki/File:Example.jpg"
                    ),
                    "mime": "image/jpeg",
                }
            ]
            app.run(timeout=10)

            self.assertFalse(app.exception)
            search_index = next(
                index
                for index, button in enumerate(app.button)
                if button.label == "Rechercher les médias de cet article"
            )
            app.button[search_index].click().run(timeout=10)

        self.assertFalse(app.exception)
        media = app.session_state["generation_history"][0]["media"]
        self.assertEqual(len(media), 2)
        self.assertEqual(media[0]["query"], "pytest")
        self.assertEqual(media[1]["query"], "pytest Configuration")
        self.assertEqual(media[0]["images"][0]["title"], "Example.jpg")
        self.assertTrue(all(section["links"]["youtube"] for section in media))
        markdown_values = [item.value for item in app.markdown]
        self.assertTrue(
            any("▶ Vidéos YouTube" in value for value in markdown_values),
            markdown_values,
        )