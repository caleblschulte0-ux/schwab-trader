import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import monitor


class MonitorTests(unittest.TestCase):
    def test_flags_market_and_holding_drops_only(self):
        prev = {"SPY": 100.0, "QQQ": 100.0, "XLE": 50.0, "GLD": 200.0}
        now = {"SPY": 96.5, "QQQ": 99.0, "XLE": 46.0, "GLD": 199.0}
        flags = monitor.evaluate(now, prev, ["XLE", "GLD"])
        self.assertEqual(len(flags), 2)
        self.assertTrue(flags[0].startswith("SPY -3.5%"))
        self.assertTrue(flags[1].startswith("holding XLE -8.0%"))

    def test_quiet_day(self):
        self.assertEqual(monitor.evaluate({"SPY": 99.5}, {"SPY": 100.0}, []), [])


if __name__ == "__main__":
    unittest.main()
