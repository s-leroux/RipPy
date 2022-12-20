import unittest
from rip import ffmpeg

class TestFfmpeg(unittest.TestCase):
    def setUp(self):
        pass

    def test_1(self):
        ff = ffmpeg.new()

        cmd = ff.cmd()
        self.assertRegex(cmd, r"\s-y\b")
        self.assertRegex(cmd, r"\s-nostdin\b")

if __name__ == '__main__':
    unittest.main()
