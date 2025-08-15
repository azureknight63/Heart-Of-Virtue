import os, sys, tempfile, pickle, unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import secure_pickle  # noqa: E402
from player import Player  # noqa: E402


class DummyClass:  # purposefully outside allow-list packages
    def __init__(self):
        self.value = 42


class TestSecurePickle(unittest.TestCase):
    def setUp(self):
        secure_pickle.EVENT_LOG.clear()

    def test_allowlist_player_strict(self):
        p = Player()
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            pickle.dump(p, tf, pickle.HIGHEST_PROTOCOL)
            tf.flush()
            fname = tf.name
        try:
            obj = secure_pickle.load(fname, strict=True)
            self.assertIsInstance(obj, Player)
            # No rejection/placeholder events expected
            self.assertFalse(any(ev['type'] in ('reject', 'placeholder') for ev in secure_pickle.EVENT_LOG))
        finally:
            os.remove(fname)

    def test_reject_unknown_strict(self):
        d = DummyClass()
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            pickle.dump(d, tf, pickle.HIGHEST_PROTOCOL)
            tf.flush()
            fname = tf.name
        try:
            with self.assertRaises(secure_pickle.RestrictedUnpicklingError):
                secure_pickle.load(fname, strict=True)
            self.assertTrue(any(ev['type'] == 'reject' for ev in secure_pickle.EVENT_LOG))
        finally:
            os.remove(fname)

    def test_placeholder_non_strict(self):
        d = DummyClass()
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            pickle.dump(d, tf, pickle.HIGHEST_PROTOCOL)
            tf.flush()
            fname = tf.name
        try:
            obj = secure_pickle.load(fname, strict=False)
            # Placeholder should have attribute set
            self.assertTrue(hasattr(obj, '_legacy_placeholder'))
            self.assertTrue(any(ev['type'] == 'placeholder' for ev in secure_pickle.EVENT_LOG))
        finally:
            os.remove(fname)


if __name__ == '__main__':
    unittest.main()

