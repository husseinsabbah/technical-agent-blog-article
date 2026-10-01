import asyncio
import os
from pathlib import Path
from datetime import datetime
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from blog_agent.agent import root_agent


PROJECT_ROOT = Path(__file__).resolve().parent
APP_NAME = "blog_agent"
AGENT_ENV = PROJECT_ROOT / "blog_agent" / ".env"
OUTPUT_KEYS = ("blog_outline", "blog_post", "quality_review")
MAX_HISTORY_ITEMS = 20


def clear_generation_history() -> None:
    st.session_state["generation_history"] = []
    st.session_state.pop("history_selection", None)


def generate_blog(topic: str) -> dict[str, str]:
    load_dotenv(AGENT_ENV)
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY est absente de blog_agent/.env.")

    async def run_workflow() -> dict[str, str]:
        session_service = InMemorySessionService()
        user_id = "local_user"
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
        )
        runner = Runner(
            agent=root_agent,
            app_name=APP_NAME,
            session_service=session_service,
        )
        message = types.Content(
            role="user",
            parts=[types.Part(text=topic)],
        )

        async for _ in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=message,
        ):
            pass

        completed_session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session.id,
        )
        if completed_session is None:
            raise RuntimeError("La session ADK s’est terminée sans résultat.")

        return {
            key: str(completed_session.state.get(key, ""))
            for key in OUTPUT_KEYS
        }

    return asyncio.run(run_workflow())


st.set_page_config(page_title="Blog agent", page_icon=":material/article:")
st.session_state.setdefault("generation_history", [])
st.title("Atelier d’articles techniques")
st.caption("Planification · rédaction · revue")

with st.form("blog_topic_form", border=False):
    topic = st.text_input(
        "Sujet technique",
        placeholder="Ex. Tester une API FastAPI avec pytest",
    )
    submitted = st.form_submit_button("Générer l’article", type="primary")

if submitted:
    if not topic.strip():
        st.error("Saisis un sujet technique.")
    else:
        try:
            with st.spinner("Les trois étapes sont en cours…"):
                result = generate_blog(topic.strip())
                generation_id = uuid4().hex
                entry = {
                    "id": generation_id,
                    "topic": topic.strip(),
                    "created_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
                    "outputs": result,
                }
                history = st.session_state["generation_history"]
                history.insert(0, entry)
                del history[MAX_HISTORY_ITEMS:]
                st.session_state["history_selection"] = generation_id
        except Exception as error:
            message = str(error)
            if "429" in message or "RESOURCE_EXHAUSTED" in message:
                st.error("Quota Gemini atteint. Vérifie les limites du modèle avant de réessayer.")
            elif "503" in message or "UNAVAILABLE" in message:
                st.error("Gemini est temporairement indisponible. Réessaie plus tard.")
            else:
                st.error(f"La génération a échoué : {message}")

history = st.session_state["generation_history"]
if history:
    with st.sidebar:
        st.subheader("Historique")
        st.caption("Temporaire : limité à cet onglet et à 20 articles.")
        history_ids = [entry["id"] for entry in history]
        selected_id = st.selectbox(
            "Articles générés",
            options=history_ids,
            format_func=lambda item_id: next(
                f"{entry['created_at']} · {entry['topic']}"
                for entry in history
                if entry["id"] == item_id
            ),
            key="history_selection",
        )
        st.button(
            "Effacer l’historique",
            icon=":material/delete_sweep:",
            on_click=clear_generation_history,
        )

    selected_entry = next(entry for entry in history if entry["id"] == selected_id)
    generation = selected_entry["outputs"]
    st.subheader(selected_entry["topic"])
    st.caption(f"Généré le {selected_entry['created_at']}")
    plan_tab, article_tab, review_tab = st.tabs(["Plan", "Article", "Revue"])

    with plan_tab:
        if generation["blog_outline"]:
            st.markdown(generation["blog_outline"])
        else:
            st.warning("Aucun plan n’a été retourné.")

    with article_tab:
        if generation["blog_post"]:
            st.markdown(generation["blog_post"])
            st.download_button(
                "Télécharger l’article",
                data=generation["blog_post"],
                file_name=f"article-{selected_entry['id'][:8]}.md",
                mime="text/markdown",
                key=f"download_{selected_entry['id']}",
                icon=":material/download:",
            )
        else:
            st.warning("Aucun article n’a été retourné.")

    with review_tab:
        st.caption("La revue est générée par le modèle et ne remplace pas une vérification des faits.")
        if generation["quality_review"]:
            review = generation["quality_review"]
            verdict = review.splitlines()[0].strip().upper()
            if verdict.startswith("NEEDS_REVIEW"):
                st.warning(review)
            elif verdict.startswith("PASS"):
                st.success(review)
            else:
                st.info(review)
        else:
            st.warning("Aucun rapport de revue n’a été retourné.")