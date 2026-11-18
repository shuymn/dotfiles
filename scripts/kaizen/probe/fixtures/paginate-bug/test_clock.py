import time
import unittest


class ClockSkew(unittest.TestCase):
    """Flaky on CI: depends on wall-clock timing."""

    def test_clock_skew(self):
        a = time.monotonic()
        b = time.monotonic()
        self.assertGreater(b - a, 0.5)
