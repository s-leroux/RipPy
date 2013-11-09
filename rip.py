import re
from itertools import chain
from subprocess import Popen,call,PIPE

PARTIAL = True

MPLAYER_GET_METADATA = [
  "mplayer", 
    "-vo", "null", 
    "-ao", "null", 
    "-frames", "0", 
    "-identify"
  ]
MPLAYER_METADATA_RE = re.compile("ID_(\w+)=(.*)")
MPLAYER_AUDIO_RE = re.compile(
     "audio stream: (\d+) format: (.+) language: (\w+) aid: (\d+).")


class Metadata:
    def __init__(self, fName):
        self._fName = fName
        self._metadata = {}
        self._aid = {}

        proc = Popen(chain(MPLAYER_GET_METADATA, [fName]),
                     stdout = PIPE,
                     universal_newlines = True)
        for line in proc.stdout:
            match = MPLAYER_METADATA_RE.match(line)
            if match:
                key, value = match.group(1,2)
                self._metadata[key] = value
                continue

            match = MPLAYER_AUDIO_RE.match(line)
            if match:
                idx, fmt, lang, aid = match.groups()
                self._aid[idx] = lang
                continue

            print("OUT:",line.strip())
                

    def audio_track_by_lang(self, lang):
        for idx, l in self._aid.items():
            if lang == l:
                return idx

        return None

    def audio_tracks(self):
        return self._aid

    def title(self):
        """Returns the disk title (based on DVD_VOLUME_ID)
        """
        vid = self._metadata["DVD_VOLUME_ID"]
        return vid if vid else "NO_NAME"

def rip(meta):
    outfile = meta.title() + ".vob"

    cmd = ["mplayer",
            meta._fName,
            "-dumpstream", "-dumpfile",
            outfile]
    if PARTIAL:
        cmd.extend(["-endpos","10:00"])

    call(cmd)

meta = Metadata("dvd://1")
print(meta._metadata)
print(meta._aid)
print("fr is track:", meta.audio_track_by_lang("fr"))
print("volume title is:", meta.title())

print("========= RIP ==========")
rip(meta)
