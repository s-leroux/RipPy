import re
from itertools import chain
from subprocess import Popen,PIPE

MPLAYER_GET_METADATA = [
  "mplayer", 
    "-vo", "null", 
    "-ao", "null", 
    "-frames", "0", 
    "-identify"
  ]
MPLAYER_METADATA_RE = re.compile("ID_(\w+)=(.*)")

def collectMetadata(file):
    result = {}

    proc = Popen(chain(MPLAYER_GET_METADATA, [file]),
                 stdout = PIPE,
                 universal_newlines = True)
    for line in proc.stdout:
        match = MPLAYER_METADATA_RE.match(line)
        if match:
            result[match.group(1)] = match.group(2)

    print(result)

collectMetadata("dvd://1")

