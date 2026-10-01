from google.adk.agents import Agent, SequentialAgent
from google.adk.workflow import RetryConfig

MODEL = "gemini-3.5-flash-lite"

blog_planner = Agent(
    name="blog_planner",
    model=MODEL,
    description="Creates a practical outline for a technical blog post.",
    instruction="""Create a clear, skimmable Markdown outline for the topic in the user's request.
Include a title, a short introduction, 4-6 main sections with 2-3 bullets each, and a conclusion.
Return only the outline.""",
    output_key="blog_outline",
)

blog_writer = Agent(
    name="blog_writer",
    model=MODEL,
    description="Writes a technical blog post from the approved outline.",
    instruction="""Write a complete Markdown article about the user's requested topic, following this outline:

{blog_outline}

Write for software engineers. Explain both how and why, include concise code examples when useful,
and use clear H2/H3 headings. When discussing asynchronous tests, distinguish pytest itself from
plugins such as AnyIO or pytest-asyncio. Keep code examples internally consistent and state assumptions.
For React, do not recommend useMemo/useCallback by default; explain profiling and React Compiler
context when relevant.
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
    description="Reviews the generated article against its outline and quality criteria.",
    instruction="""Review the article against the requested topic and this outline:

{blog_outline}

Article to review:
{blog_post}

Check that the article follows the outline, has a title, introduction, conclusion, and the requested
alternate titles and social-media hooks. Assess clarity and technical consistency. For code examples,
check imports, definitions, fixtures, request payloads, and assertions for consistency; flag undefined
application-specific names unless the snippet is labelled illustrative. State when an example was not
executed. For React content, check that useMemo/useCallback are not presented as default optimizations,
and that useEffect data-fetching examples address cleanup, stale responses, and loading/error states.
Distinguish pytest itself from async plugins such as AnyIO or pytest-asyncio.
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
    description="Plans and writes a technical blog post, then reviews its quality.",
    sub_agents=[blog_planner, blog_writer, blog_reviewer],
)
