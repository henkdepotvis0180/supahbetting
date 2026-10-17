import math
import unittest
from supahbetting.model_calibration import temperature_scale, fit_temperature


class CalibrationTests(unittest.TestCase):
    def test_identity(self):
        p = {"home": .5, "draw": .3, "away": .2}
        result = temperature_scale(p, 1.0)
        for k in p:
            self.assertAlmostEqual(result[k], p[k])

    def test_normalized(self):
        p = {"home": .8, "draw": .1, "away": .1}
        q = temperature_scale(p, 1.2)
        self.assertAlmostEqual(sum(q.values()), 1)
        self.assertLess(q["home"], p["home"])

    def test_invalid(self):
        with self.assertRaises(ValueError):
            temperature_scale({"home": 1, "draw": 0, "away": 0}, 0)
        with self.assertRaises(ValueError):
            fit_temperature([])

    def test_validation_only(self):
        p = {"home": .7, "draw": .2, "away": .1}
        t = fit_temperature([(p, "home")] * 10)
        self.assertTrue(math.isfinite(t))


if __name__ == "__main__":
    unittest.main()
