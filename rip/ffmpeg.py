#
# Utilities to create and run ffmpeg commands from Python
#
class Ffmpeg:
    def __init__(self):
        self.inputs = []
        self.output = None

    def newInput(self, fname):
        input = dict(opts=[], fname=fname);
        self.inputs.append(input)

        return input

    def setOutput(self, fname):
        self.output = dict(opts=[], fname=fname)
        return self.output

    def cmd(self):
        cmd = "ffmpeg -nostdin -y"
        for i in self.inputs:
            cmd += " -i {fname}".format(i)

        if self.output:
            cmd += " {fname}".format(self.output)

        return cmd

def new():
    return Ffmpeg()
