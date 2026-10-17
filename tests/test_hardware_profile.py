import unittest
from unittest.mock import patch
from supahbetting.hardware_profile import detect, select_workers


class HardwareProfileTests(unittest.TestCase):
    def test_small_pc(self):
        self.assertEqual(select_workers(2, 4), 1)

    def test_large_pc_capped(self):
        self.assertEqual(select_workers(24, 32), 16)

    def test_low_memory_limits_workers(self):
        self.assertEqual(select_workers(24, 6), 4)

    def test_fallback(self):
        with patch("supahbetting.hardware_profile._windows_details", return_value={}):
            with patch("supahbetting.hardware_profile.os.cpu_count", return_value=8):
                result = detect()
        self.assertEqual(result["recommended_workers"], 6)
        self.assertFalse(result["gpu_acceleration_enabled"])


if __name__ == "__main__":
    unittest.main()
