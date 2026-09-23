"""Contract tests for alpaca.py against Alpaca's documented response shapes.
No network: urllib is replaced by a fake that serves canned JSON per URL and records
every request (method, URL, body, headers)."""
import io
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import alpaca
from alpaca import Alpaca, AlpacaError


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Server:
    """routes: list of (predicate(url, method) -> bool, responder(req) -> (status, obj))"""

    def __init__(self):
        self.routes = []
        self.log = []

    def add(self, substr, obj=None, status=200, method=None, fn=None):
        self.routes.append((substr, method, obj, status, fn))

    def __call__(self, req, timeout=None):
        url = req.full_url
        body = json.loads(req.data.decode()) if req.data else None
        self.log.append((req.get_method(), url, body, dict(req.header_items())))
        for substr, method, obj, status, fn in self.routes:
            if substr in url and (method is None or method == req.get_method()):
                if fn:
                    status, obj = fn(url, body)
                if status >= 400:
                    raise urllib.error.HTTPError(url, status, "err", {}, io.BytesIO(json.dumps(obj).encode()))
                return FakeResp(json.dumps(obj).encode())
        raise AssertionError(f"unexpected request {req.get_method()} {url}")


class AlpacaClientTests(unittest.TestCase):
    def setUp(self):
        self.srv = Server()
        self.p = mock.patch.object(alpaca.urllib.request, "urlopen", self.srv)
        self.p.start()
        self.sleep = mock.patch.object(alpaca.time, "sleep", lambda s: None)
        self.sleep.start()
        self.api = Alpaca("KEY", "SECRET", paper=True)

    def tearDown(self):
        self.p.stop()
        self.sleep.stop()

    def test_headers_and_base_urls(self):
        self.srv.add("/v2/account", {"equity": "1000", "cash": "1000"})
        self.api.account()
        m, url, body, hdr = self.srv.log[-1]
        self.assertTrue(url.startswith("https://paper-api.alpaca.markets/v2/account"))
        self.assertEqual(hdr["Apca-api-key-id"], "KEY")
        self.assertEqual(hdr["Apca-api-secret-key"], "SECRET")
        live = Alpaca("K", "S", paper=False)
        self.srv.add("/v2/clock", {"is_open": True})
        live.clock()
        self.assertTrue(self.srv.log[-1][1].startswith("https://api.alpaca.markets/"))

    def test_submit_order_bodies(self):
        self.srv.add("/v2/orders", {"id": "o1", "status": "accepted"}, method="POST")
        self.api.submit_order("SPY", "buy", notional=123.456, client_order_id="2026-09-22-SPY-buy-123")
        body = self.srv.log[-1][2]
        self.assertEqual(body, {"symbol": "SPY", "side": "buy", "type": "market", "time_in_force": "day",
                                "notional": "123.46", "client_order_id": "2026-09-22-SPY-buy-123"})
        self.api.submit_order("GLD", "buy", qty=3)
        self.assertEqual(self.srv.log[-1][2]["qty"], "3")
        self.assertNotIn("notional", self.srv.log[-1][2])
        with self.assertRaises(ValueError):
            self.api.submit_order("SPY", "buy")
        with self.assertRaises(ValueError):
            self.api.submit_order("SPY", "buy", notional=1, qty=1)

    def test_wait_for_fill_polls_until_terminal(self):
        states = iter(["new", "partially_filled", "filled"])
        self.srv.add("/v2/orders/o1", fn=lambda u, b: (200, {"id": "o1", "status": next(states), "filled_qty": "1"}))
        o = self.api.wait_for_fill("o1", timeout_s=5, poll_s=0)
        self.assertEqual(o["status"], "filled")
        self.assertEqual(sum(1 for m, u, _, _ in self.srv.log if "/v2/orders/o1" in u), 3)

    def test_daily_bars_pagination_and_feed_fallback(self):
        pages = {None: ({"SPY": [{"t": "2026-09-18T04:00:00Z", "c": 100.0}], "GLD": [{"t": "2026-09-18T04:00:00Z", "c": 50.0}]}, "tok1"),
                 "tok1": ({"SPY": [{"t": "2026-09-19T04:00:00Z", "c": 101.0}]}, None)}

        def bars(url, body):
            if "feed=sip" in url:
                return 403, {"message": "subscription does not permit querying recent SIP data"}
            tok = None
            if "page_token=" in url:
                tok = url.split("page_token=")[1].split("&")[0]
            data, nxt = pages[tok]
            return 200, {"bars": data, "next_page_token": nxt}
        self.srv.add("/v2/stocks/bars", fn=bars)
        out = self.api.daily_bars(["SPY", "GLD"], start="2026-01-01", end="2026-09-21")
        self.assertEqual(out["SPY"], [("2026-09-18", 100.0), ("2026-09-19", 101.0)])
        self.assertEqual(out["GLD"], [("2026-09-18", 50.0)])
        urls = [u for m, u, _, _ in self.srv.log if "/v2/stocks/bars" in u]
        self.assertIn("feed=sip", urls[0])
        self.assertTrue(all("feed=iex" in u for u in urls[1:]))
        self.assertIn("adjustment=all", urls[-1])
        self.assertIn("symbols=GLD%2CSPY", urls[-1])

    def test_latest_prices_precedence(self):
        self.srv.add("/v2/stocks/snapshots", {
            "SPY": {"latestTrade": {"p": 500.5}, "dailyBar": {"c": 499.0}},
            "GLD": {"latestTrade": {}, "minuteBar": {"c": 180.25}},
            "TLT": {"dailyBar": {"c": 90.0}},
            "BAD": {},
        })
        out = self.api.latest_prices(["SPY", "GLD", "TLT", "BAD"])
        self.assertEqual(out, {"SPY": 500.5, "GLD": 180.25, "TLT": 90.0})

    def test_fills_and_cash_flows_paging(self):
        page1 = [{"id": f"f{i}", "symbol": "SPY", "side": "buy", "qty": "1", "price": "10", "transaction_time": "2026-09-01T15:00:00Z"} for i in range(100)]
        page2 = [{"id": "f100", "symbol": "SPY", "side": "sell", "qty": "1", "price": "11", "transaction_time": "2026-09-02T15:00:00Z"}]

        def fills(url, body):
            return 200, (page2 if "page_token=f99" in url else page1)
        self.srv.add("/v2/account/activities/FILL", fn=fills)
        out = self.api.fills(after="2026-01-01")
        self.assertEqual(len(out), 101)
        self.srv.add("/v2/account/activities?", [{"activity_type": "CSD", "net_amount": "500"},
                                                 {"activity_type": "CSW", "net_amount": "-125.5"},
                                                 {"activity_type": "JNLC", "net_amount": None}])
        self.assertAlmostEqual(self.api.cash_flows(after="2026-09-01"), 374.5)
        self.assertIn("activity_types=CSD%2CCSW%2CJNLC%2CACATC%2CACATS", self.srv.log[-1][1])

    def test_rate_limit_retries_then_succeeds(self):
        calls = {"n": 0}

        def flaky(url, body):
            calls["n"] += 1
            return (429, {"message": "too many requests"}) if calls["n"] < 3 else (200, {"is_open": True})
        self.srv.add("/v2/clock", fn=flaky)
        self.assertTrue(self.api.clock()["is_open"])
        self.assertEqual(calls["n"], 3)

    def test_client_errors_raise_immediately(self):
        self.srv.add("/v2/orders", {"code": 40310000, "message": "insufficient buying power"}, status=403, method="POST")
        with self.assertRaises(AlpacaError) as cm:
            self.api.submit_order("SPY", "buy", notional=5)
        self.assertEqual(cm.exception.status, 403)
        self.assertIn("insufficient", str(cm.exception))
        self.assertEqual(sum(1 for m, u, _, _ in self.srv.log if m == "POST"), 1)  # no retry on 4xx

    def test_close_and_cancel_endpoints(self):
        self.srv.add("/v2/positions/SPY", {"id": "o9", "status": "accepted"}, method="DELETE")
        self.srv.add("/v2/positions?", [], method="DELETE")
        self.srv.add("/v2/orders", [], method="DELETE")
        self.api.close_position("SPY")
        self.assertEqual(self.srv.log[-1][0], "DELETE")
        self.api.close_all_positions()
        self.assertIn("cancel_orders=true", self.srv.log[-1][1])
        self.api.cancel_all_orders()
        self.assertEqual(self.srv.log[-1][0], "DELETE")


if __name__ == "__main__":
    unittest.main()
