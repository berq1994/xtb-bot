from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from radar.agent import AgentResponse, RadarAgent
from radar.config import RadarConfig


class AgentCommandRoutingTests(TestCase):
    def setUp(self) -> None:
        self.agent = RadarAgent(RadarConfig())
        self.now = datetime(2026, 1, 1, 12, 0, 0)

    def test_news_command_routes_to_news_handler(self) -> None:
        expected = AgentResponse("News", "ok")
        with patch.object(RadarAgent, "news", return_value=expected) as news_mock:
            resp = self.agent.handle("news", now=self.now)
        self.assertEqual(resp, expected)
        news_mock.assert_called_once_with(self.now)

    def test_explain_without_ticker_returns_helpful_message(self) -> None:
        resp = self.agent.handle("explain", now=self.now)
        self.assertEqual(resp.title, "Explain")
        self.assertIn("Chybí ticker", resp.markdown)

    def test_explain_with_ticker_routes_to_explain_handler(self) -> None:
        expected = AgentResponse("Explain", "ok")
        with patch.object(RadarAgent, "explain", return_value=expected) as explain_mock:
            resp = self.agent.handle("explain nvda", now=self.now)
        self.assertEqual(resp, expected)
        explain_mock.assert_called_once_with("nvda", self.now)
