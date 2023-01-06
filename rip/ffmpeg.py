#
# Utilities to create and run ffmpeg commands from Python
#

from pipes import quote

class Ffmpeg:
    def __init__(self):
        self.inputs = []
        self.output = None

    def newInput(self, fname):
        input = dict(opts=[], fname=quote(fname));
        self.inputs.append(input)

        return input

    def countInputs(self):
        return len(self.inputs)

    def setOutput(self, fname):
        self.output = dict(opts=[], fname=quote(fname))
        return self.output

    def cmd(self):
        cmd = "ffmpeg -nostdin -y"
        for input in self.inputs:
            for opt in input["opts"]:
              cmd += " " + " ".join([quote(str(i)) for i in opt])

            cmd += " -i {fname}".format_map(input)

        if self.output:
            for opt in self.output["opts"]:
              cmd += " " + " ".join([quote(str(i)) for i in opt])

            cmd += " {fname}".format_map(self.output)

        return cmd + "\n"

def new():
    return Ffmpeg()
