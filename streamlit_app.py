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
CATEGORY_PROMPT = "Choisis une catégorie"
SUBCATEGORY_PROMPT = "Choisis une sous-catégorie"
AUDIENCE_DEFAULT = "Grand public curieux"
AUDIENCES = [
    "Grand public curieux",
    "Débutants",
    "Amateurs éclairés / niveau intermédiaire",
    "Professionnels / praticiens",
    "Experts / spécialistes",
    "Décideurs / porteurs de projet",
]
SUBCATEGORIES = {
    "Design": [
        "Identité visuelle et branding",
        "Graphisme et design éditorial",
        "UI/UX et produit numérique",
        "Design web et interfaces",
        "Illustration",
        "Packaging",
        "Design produit et industriel",
        "Design intérieur",
        "Motion design",
        "Mode et textile",
        "Photographie et direction artistique",
        "Autre design",
    ],
    "Impression": [
        "Impression numérique",
        "Impression offset",
        "Grand format et signalétique",
        "Sérigraphie",
        "Impression textile (DTF, DTG, flex)",
        "Sublimation",
        "Impression 3D",
        "Étiquettes et adhésifs",
        "Livres, édition et reliure",
        "Finition et façonnage",
        "Autre impression",
    ],
    "Librairie": [
        "Littérature générale et romans",
        "Science-fiction et fantasy",
        "BD et manga",
        "Livres jeunesse",
        "Scolaire et universitaire",
        "Sciences, informatique et technique",
        "Histoire, société et actualité",
        "Art, photographie et beaux livres",
        "Développement personnel et bien-être",
        "Langues, dictionnaires et méthodes",
        "Poésie et théâtre",
        "Gestion et animation de librairie",
        "Autre librairie",
    ],
    "Jeux et jouets": [
        "Jeux de société",
        "Jeux de cartes et TCG",
        "Puzzles et casse-têtes",
        "Jouets éducatifs et STEM",
        "Jeux de construction",
        "Figurines et objets de collection",
        "Poupées et jeux d’imitation",
        "Jeux d’extérieur et de sport",
        "Jouets petite enfance",
        "Jeux vidéo",
        "Autre jeu ou jouet",
    ],
    "IA": [
        "IA générative et LLM",
        "Agents IA et automatisation",
        "Machine learning",
        "Deep learning",
        "Traitement du langage (NLP)",
        "Vision par ordinateur",
        "Voix et audio",
        "Robotique",
        "MLOps et infrastructures IA",
        "IA responsable, sécurité et gouvernance",
        "Applications de l’IA par secteur",
        "Autre sujet IA",
    ],
    "Construction": [
        "Architecture et conception",
        "Études, plans et permis",
        "Fondations et gros œuvre",
        "Structure et charpente",
        "Maçonnerie et enveloppe du bâtiment",
        "Second œuvre et finitions",
        "Électricité, plomberie et CVC",
        "Rénovation et réhabilitation",
        "Matériaux de construction",
        "Construction durable et efficacité énergétique",
        "BIM et gestion de chantier",
        "Infrastructures et travaux publics",
        "Sécurité et réglementation du chantier",
        "Autre construction",
    ],
}


def clear_generation_history() -> None:
    st.session_state["generation_history"] = []
    st.session_state.pop("history_selection", None)


def build_blog_request(
    category: str,
    subcategory: str,
    audience: str,
    topic: str,
) -> str:
    return (
        f"Catégorie principale : {category}\n"
        f"Sous-catégorie : {subcategory}\n"
        f"Public visé : {audience}\n"
        f"Sujet ou angle demandé : {topic}\n\n"
        "Adapte le vocabulaire, le niveau de détail, les exemples et les prérequis au public visé. "
        "Rédige l’article dans la langue de la demande."
    )


def generate_blog(
    category: str,
    subcategory: str,
    audience: str,
    topic: str,
) -> dict[str, str]:
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
            parts=[
                types.Part(
                    text=build_blog_request(category, subcategory, audience, topic)
                )
            ],
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
st.title("Choisis le type de sujet")

with st.container(horizontal=True):
    category = st.selectbox(
        "Catégorie principale",
        options=[CATEGORY_PROMPT, *SUBCATEGORIES],
        key="category",
    )
    if category == CATEGORY_PROMPT:
        subcategory = st.selectbox(
            "Sous-catégorie",
            options=[SUBCATEGORY_PROMPT],
            disabled=True,
            key="subcategory_pending",
        )
    else:
        subcategory = st.selectbox(
            "Sous-catégorie",
            options=SUBCATEGORIES[category],
            key=f"subcategory_{category}",
        )
    audience = st.selectbox(
        "Public visé",
        options=AUDIENCES,
        index=AUDIENCES.index(AUDIENCE_DEFAULT),
        key="audience",
    )

st.caption("Le plan, l’article et la revue s’adaptent au sujet et au public choisis.")

with st.form("blog_topic_form", border=False):
    topic = st.text_input(
        "Sujet ou angle précis",
        placeholder="Ex. Comment choisir un papier pour une affiche grand format",
    )
    submitted = st.form_submit_button("Générer l’article", type="primary", icon=":material/auto_awesome:")

if submitted:
    if category == CATEGORY_PROMPT:
        st.error("Choisis une catégorie principale.")
    elif not topic.strip():
        st.error("Saisis un sujet ou un angle précis.")
    else:
        try:
            with st.spinner("Les trois étapes sont en cours…"):
                result = generate_blog(category, subcategory, audience, topic.strip())
                generation_id = uuid4().hex
                entry = {
                    "id": generation_id,
                    "topic": topic.strip(),
                    "category": category,
                    "subcategory": subcategory,
                    "audience": audience,
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
                f"{entry['created_at']} · "
                f"{entry.get('category', 'Sans catégorie')} / "
                f"{entry.get('subcategory', 'Sans sous-catégorie')} · "
                f"{entry.get('audience', 'Public non précisé')} · {entry['topic']}"
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
    st.caption(
        f"{selected_entry.get('category', 'Sans catégorie')} · "
        f"{selected_entry.get('subcategory', 'Sans sous-catégorie')} · "
        f"{selected_entry.get('audience', 'Public non précisé')} · "
        f"Généré le {selected_entry['created_at']}"
    )
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