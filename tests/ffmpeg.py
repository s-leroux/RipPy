import unittest
from rip import ffmpeg

class TestFfmpeg(unittest.TestCase):
    def setUp(self):
        pass

    def test_0(self):
        """Comand is terminated by \\n
        """
        ff = ffmpeg.new()

        cmd = ff.cmd()
        self.assertRegex(cmd, r"\n$")

    def test_1(self):
        ff = ffmpeg.new()

        cmd = ff.cmd()
        self.assertRegex(cmd, r"\s-y\b")
        self.assertRegex(cmd, r"\s-nostdin\b")

    def test_2(self):
        ff = ffmpeg.new()
        ff.newInput("input1")
        ff.newInput("input2")

        cmd = ff.cmd()
        self.assertRegex(cmd, r"\s-i\s+input1\b")
        self.assertRegex(cmd, r"\s-i\s+input2\b")

    def test_3(self):
        """ Accept integers as options
        """
        ff = ffmpeg.new()
        input = ff.newInput("input")
        input["opts"].append(("-ss", 0))

        output = ff.setOutput("output")
        output["opts"].append(("-to", 1))

        cmd = ff.cmd()
        self.assertRegex(cmd, r"\s-ss\s+0\s+-i\s+input\b")
        self.assertRegex(cmd, r"\s-to\s+1\s+output\b")

    def test_4(self):
        ff = ffmpeg.new()
        input = ff.newInput("input1")
        input["opts"].append(("-ss", "00:00:00"))

        input = ff.newInput("input2")
        input["opts"].append(("-to", "01:00:00"))

        cmd = ff.cmd()
        self.assertRegex(cmd, r"\s-ss\s+00:00:00\s+-i\s+input1\b")
        self.assertRegex(cmd, r"\s-to\s+01:00:00\s+-i\s+input2\b")

    def test_5(self):
        ff = ffmpeg.new()
        output = ff.setOutput("out")
        output["opts"].append(("-ss", "00:00:00"))
        output["opts"].append(("-to", "01:00:00"))

        cmd = ff.cmd()
        self.assertRegex(cmd, r"\s-ss\s+00:00:00\s+-to\s+01:00:00\s+out\b")

if __name__ == '__main__':
    unittest.main()
