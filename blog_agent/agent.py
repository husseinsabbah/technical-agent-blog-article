from google.adk.agents import Agent, SequentialAgent
from google.adk.workflow import RetryConfig

MODEL = "gemini-3.5-flash-lite"

blog_planner = Agent(
    name="blog_planner",
    model=MODEL,
    description="Creates a practical outline for the selected category and topic.",
    instruction="""Read the main category, subcategory, intended audience, and specific topic in the user's request.
Treat the selected category and subcategory as the intended domain. Shape the outline's depth and
prerequisites for the selected audience. Create a clear, skimmable
Markdown outline with a title, short introduction, 4-6 main sections with 2-3 bullets each, and
a conclusion. Choose sections and examples that fit that domain; do not force a software-engineering
structure onto another category. Return only the outline.""",
    output_key="blog_outline",
)

blog_writer = Agent(
    name="blog_writer",
    model=MODEL,
    description="Writes a blog post adapted to the selected category and approved outline.",
    instruction="""Write a complete Markdown article about the user's requested topic, following this outline:

{blog_outline}

Write in French unless the request asks for another language. Adapt vocabulary, depth, assumed knowledge,
tone, and examples to the explicitly selected audience as well as the selected category; do not default
to developers or professionals unless they were selected. Explain how and why, and use clear H2/H3 headings.
Include code only when it fits the
topic. For printing, state that production settings depend on equipment and materials. For games and toys,
avoid unsupported age-rating or safety claims. For AI, flag fast-changing model or product claims that
need current sources. For construction, flag code, structural, electrical, and safety advice for local
professional verification; do not present jurisdiction-specific rules as universal.

For software topics, keep code examples internally consistent and state assumptions. When discussing
asynchronous tests, distinguish pytest itself from plugins such as AnyIO or pytest-asyncio. For React,
do not recommend useMemo/useCallback by default; explain profiling and React Compiler context when relevant.
Data-fetching examples using useEffect should cover cleanup, stale responses, and loading/error states;
localStorage examples should state client-only assumptions when applicable. Label snippets with undefined
application-specific names as illustrative, not runnable. Avoid unrequested calendar years throughout
the article. Finish with a conclusion, 3 alternate titles, and 2 short social-media hooks.
Return only the article in Markdown.""",
    output_key="blog_post",
    retry_config=RetryConfig(
        max_attempts=3,
        initial_delay=2.0,
        max_delay=8.0,
        backoff_factor=2.0,
        jitter=0.2,
        exceptions=["ServerError"],
    ),
)

blog_reviewer = Agent(
    name="blog_reviewer",
    model=MODEL,
    description="Reviews the generated article against its category, outline, and quality criteria.",
    instruction="""Review the article against the requested topic and this outline:

{blog_outline}

Article to review:
{blog_post}

Check that the article follows the outline and fits the explicitly selected audience, has a title,
introduction, conclusion, and the requested alternate titles and social-media hooks. Assess fit for the
selected category, clarity, and consistency.
For printing, flag equipment- or material-dependent specifications. For games and toys, flag safety and
age-rating claims. For AI, flag time-sensitive model claims. For construction, flag local codes, structural,
electrical, and safety advice for expert verification. Do not claim to verify facts using external sources.
For code examples, check imports, definitions, fixtures, request payloads, and assertions for consistency;
flag undefined application-specific names unless the snippet is labelled illustrative. State when an
example was not executed. For React, check memoization guidance and useEffect cleanup; for async tests,
distinguish pytest itself from plugins such as AnyIO or pytest-asyncio.
Do not claim to verify facts using external sources. Flag specific claims or examples that need manual
verification. Scan the entire article, including titles, body, examples, and hooks, for
unrequested calendar years or time-sensitive claims. Flag them as NEEDS_REVIEW unless requested by the
user or supported by a cited source.
Use NEEDS_REVIEW whenever correctness is uncertain. Return a concise report starting with either
PASS or NEEDS_REVIEW, followed by any findings.""",
    output_key="quality_review",
)

root_agent = SequentialAgent(
    name="blog_workflow",
    description="Plans, writes, and reviews a blog post for the selected category and topic.",
    sub_agents=[blog_planner, blog_writer, blog_reviewer],
)
