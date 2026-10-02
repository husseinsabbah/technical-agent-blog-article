import unittest

from google.adk.agents import SequentialAgent

from blog_agent.agent import (
    MODEL,
    blog_planner,
    blog_reviewer,
    blog_writer,
    root_agent,
)


class BlogAgentWorkflowTests(unittest.TestCase):
    def test_root_runs_planner_before_writer(self):
        self.assertIsInstance(root_agent, SequentialAgent)
        self.assertEqual(
            [agent.name for agent in root_agent.sub_agents],
            ["blog_planner", "blog_writer", "blog_reviewer"],
        )

    def test_planner_output_is_available_to_writer(self):
        self.assertEqual(blog_planner.output_key, "blog_outline")
        self.assertEqual(blog_writer.output_key, "blog_post")
        self.assertIn("{blog_outline}", blog_writer.instruction)
        self.assertEqual(blog_reviewer.output_key, "quality_review")
        self.assertIn("{blog_outline}", blog_reviewer.instruction)
        self.assertIn("{blog_post}", blog_reviewer.instruction)

    def test_both_agents_use_the_configured_model(self):
        self.assertEqual(blog_planner.model, MODEL)
        self.assertEqual(blog_writer.model, MODEL)
        self.assertEqual(blog_reviewer.model, MODEL)

    def test_writer_retries_server_errors(self):
        self.assertEqual(blog_writer.retry_config.max_attempts, 3)
        self.assertEqual(blog_writer.retry_config.exceptions, ["ServerError"])

    def test_writer_and_reviewer_check_async_testing_claims(self):
        self.assertIn("pytest itself", blog_writer.instruction)
        self.assertIn("pytest itself", blog_reviewer.instruction)
        self.assertIn("NEEDS_REVIEW whenever correctness is uncertain", blog_reviewer.instruction)

    def test_writer_avoids_unrequested_years(self):
        self.assertIn("Avoid unrequested calendar years", blog_writer.instruction)
        self.assertIn("Scan the entire article", blog_reviewer.instruction)

    def test_react_guidance_covers_common_code_pitfalls(self):
        self.assertIn("do not recommend useMemo/useCallback by default", blog_writer.instruction)
        self.assertIn("cleanup, stale responses", blog_writer.instruction)
        self.assertIn("flag undefined", blog_reviewer.instruction)

    def test_agents_adapt_to_explicitly_selected_audience(self):
        self.assertIn("intended audience", blog_planner.instruction)
        self.assertIn("explicitly selected audience", blog_writer.instruction)
        self.assertIn("explicitly selected audience", blog_reviewer.instruction)

if __name__ == "__main__":
    unittest.main()