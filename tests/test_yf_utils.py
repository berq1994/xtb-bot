from unittest import TestCase
from unittest.mock import patch

import pandas as pd

from radar import yf_utils


class YfUtilsTests(TestCase):
    def setUp(self) -> None:
        yf_utils.reset_yf_rate_limit_state()

    def test_sets_rate_limited_state_after_429(self) -> None:
        with patch("radar.yf_utils.yf.Ticker") as ticker_mock:
            ticker_mock.return_value.history.side_effect = Exception("429 Too Many Requests")
            result = yf_utils.yf_history("SPY", period="5d", interval="1d")
        self.assertIsNone(result)
        self.assertTrue(yf_utils.is_yf_rate_limited())

    def test_returns_none_when_rate_limited_without_calling_yfinance(self) -> None:
        with patch("radar.yf_utils.yf.Ticker") as ticker_mock:
            ticker_mock.return_value.history.side_effect = Exception("429 Too Many Requests")
            yf_utils.yf_history("SPY", period="5d", interval="1d")

        with patch("radar.yf_utils.yf.Ticker") as ticker_mock:
            result = yf_utils.yf_history("QQQ", period="5d", interval="1d")
        self.assertIsNone(result)
        ticker_mock.assert_not_called()

    def test_returns_dataframe_when_available(self) -> None:
        df = pd.DataFrame({"Close": [100.0, 101.0]})
        with patch("radar.yf_utils.yf.Ticker") as ticker_mock:
            ticker_mock.return_value.history.return_value = df
            result = yf_utils.yf_history("SPY", period="5d", interval="1d")
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
