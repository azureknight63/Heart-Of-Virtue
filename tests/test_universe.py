import unittest
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import universe  # noqa: E402


class TestUniverse(unittest.TestCase):
    def test_parse_hidden(self):
        cases = [
            ("", False, 0),
            ("garbage", False, 0),
            ("h+0", True, 0),
            ("h+123", True, 123),
        ]
        for setting, expected_hidden, expected_hfactor in cases:
            with self.subTest(setting=setting):
                hidden, hfactor = universe.Universe.parse_hidden(setting)
                self.assertEqual(hidden, expected_hidden)
                self.assertEqual(hfactor, expected_hfactor)


if __name__ == "__main__":
    unittest.main()
