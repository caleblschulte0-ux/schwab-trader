"""News layer: RSS parsing, strict verdict validation, defensive-only overlay, scorecard,
and the executor applying it. No network, no LLM."""
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import news
import news_brain
import news_overlay

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Nasdaq hits record - Reuters</title><pubDate>Tue, 22 Sep 2026 20:00:00 GMT</pubDate><source>Reuters</source></item>
<item><title>Nasdaq hits record - Reuters</title><pubDate>Tue, 22 Sep 2026 20:05:00 GMT</pubDate></item>
<item><title>Ancient story</title><pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate></item>
<item><title>Oil tanker seized in Strait of Hormuz</title><pubDate>Tue, 22 Sep 2026 18:00:00 GMT</pubDate></item>
</channel></rss>"""
NOW = datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc)


class CollectTests(unittest.TestCase):
    def test_parse_dedupe_and_age_filter(self):
        heads = news.collect(["XLE"], fetch=lambda url: RSS, now=NOW)
        titles = [h["title"] for h in heads]
        self.assertIn("Nasdaq hits record - Reuters", titles)
        self.assertEqual(sum(1 for t in titles if t.startswith("Nasdaq")), 1)   # de-duplicated
        self.assertNotIn("Ancient story", titles)                               # too old
        self.assertEqual([h["id"] for h in heads], list(range(1, len(heads) + 1)))

    def test_dead_sources_are_tolerated(self):
        self.assertEqual(news.collect(["XLE"], fetch=lambda url: None, now=NOW), [])
        self.assertEqual(news.parse_rss(b"not xml", "x"), [])


HEADS = [{"id": i, "title": f"headline {i}", "source": "s"} for i in range(1, 21)]
ALLOWED = {"XLE", "QQQ", "SPY", "USO"}


class VerdictTests(unittest.TestCase):
    def test_valid_verdict(self):
        text = 'Sure! {"market_risk": 2, "market_reason": "war", "market_evidence": [3, 4],' \
               ' "vetoes": [{"symbol": "xle", "reason": "oil shock", "evidence": [5]}], "summary": "s"}'
        v = news_brain.parse_verdict(text, HEADS, ALLOWED)
        self.assertEqual(v["market_risk"], 2)
        self.assertEqual(v["vetoes"][0]["symbol"], "XLE")
        self.assertEqual(v["vetoes"][0]["headlines"], ["headline 5"])

    def test_uncited_or_invented_claims_are_dropped(self):
        text = json.dumps({"market_risk": 3, "market_evidence": [999],
                           "vetoes": [{"symbol": "XLE", "evidence": []}, {"symbol": "TSLA", "evidence": [1]},
                                      {"symbol": "USO", "evidence": ["7"]}]})
        v = news_brain.parse_verdict(text, HEADS, ALLOWED)
        self.assertEqual(v["market_risk"], 0)                      # level 3 with fake evidence -> 0
        self.assertEqual([x["symbol"] for x in v["vetoes"]], ["USO"])
        self.assertEqual(len(v["dropped"]), 3)

    def test_out_of_range_and_garbage(self):
        v = news_brain.parse_verdict('{"market_risk": 9, "vetoes": "nope"}', HEADS, ALLOWED)
        self.assertEqual(v["market_risk"], 0)
        with self.assertRaises(ValueError):
            news_brain.parse_verdict("I think markets are fine", HEADS, ALLOWED)

    def test_veto_count_is_capped(self):
        vs = [{"symbol": s, "evidence": [1]} for s in ["XLE", "QQQ", "SPY", "USO"]]
        v = news_brain.parse_verdict(json.dumps({"market_risk": 0, "vetoes": vs}), HEADS, ALLOWED)
        self.assertEqual(len(v["vetoes"]), news_brain.MAX_VETOES)

    def test_prompt_contains_portfolio_and_headlines(self):
        p = news_brain.build_prompt(HEADS, {"QQQ": 0.5, "XLE": 0.1}, "2026-09-22")
        self.assertIn("QQQ 50%: Nasdaq-100 big tech", p)
        self.assertIn("5 | s |", p)


W = {"QQQ": 0.5, "XLE": 0.2, "TLT": 0.1, "BIL": 0.2}


class OverlayTests(unittest.TestCase):
    def test_stale_or_missing_verdict_is_a_noop(self):
        self.assertEqual(news_overlay.apply(W, None, "2026-09-22"), (W, []))
        self.assertEqual(news_overlay.apply(W, {"date": "2026-09-21", "market_risk": 3}, "2026-09-22")[1], [])
        self.assertEqual(news_overlay.apply(W, {"date": "2026-09-22", "market_risk": 3}, "2026-09-22", enabled=False)[1], [])

    def test_market_risk_scales_only_risk_assets(self):
        out, acts = news_overlay.apply(W, {"date": "d", "market_risk": 3}, "d")
        self.assertAlmostEqual(out["QQQ"], 0.25)
        self.assertAlmostEqual(out["XLE"], 0.10)
        self.assertAlmostEqual(out["TLT"], 0.10)          # safe asset untouched
        self.assertAlmostEqual(out["BIL"], 0.55)
        self.assertAlmostEqual(sum(out.values()), 1.0)
        self.assertEqual(len(acts), 1)
        self.assertEqual(news_overlay.apply(W, {"date": "d", "market_risk": 1}, "d")[1], [])   # level 1 informational

    def test_veto_moves_to_cash_and_never_adds(self):
        v = {"date": "d", "market_risk": 0, "vetoes": [{"symbol": "XLE", "reason": "r"}, {"symbol": "SMH", "reason": "not held"}]}
        out, acts = news_overlay.apply(W, v, "d")
        self.assertNotIn("XLE", out)
        self.assertNotIn("SMH", out)
        self.assertAlmostEqual(out["BIL"], 0.4)
        for s, w in out.items():
            if s != "BIL":
                self.assertLessEqual(w, W.get(s, 0.0) + 1e-12)

    def test_scorecard(self):
        log = [{"date": "d1", "raw": {"QQQ": 0.5, "BIL": 0.5}, "final": {"QQQ": 0.25, "BIL": 0.75},
                "prices": {"QQQ": 100.0, "BIL": 50.0}, "capital": 1000.0, "effect": None}]
        e = news_overlay.score_previous(log, {"QQQ": 90.0, "BIL": 50.0})      # QQQ fell 10%
        self.assertAlmostEqual(e["effect"], 0.025)                            # saved 2.5% of capital
        self.assertAlmostEqual(e["effect_dollars"], 25.0)
        self.assertIsNone(news_overlay.score_previous(log, {"QQQ": 80.0}))   # already scored
        sm = news_overlay.summary(log)
        self.assertEqual((sm["helped"], sm["hurt"], sm["net_dollars"]), (1, 0, 25.0))


if __name__ == "__main__":
    unittest.main()
