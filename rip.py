import re
from itertools import chain
from subprocess import Popen,call,PIPE

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

    call(cmd)
    return outfile

def lang_code(XX):
    {
        "fr": "fra",
        "en": "eng",
    }.get(XX, "")

def conv(meta,infile):
    cmd = ["avconv",
            "-i", infile,
            "-codec:v", "libx264", 
            "-pre", "slow", 
            "-b:v", "1.5M", 
            "-map", "0:v"
            "-codec:a", "copy"]
    for lang in ('fr', 'en'):
        track = meta.audio_track_by_lang(lang)
        if track is not None:
            sspec = "a:"+str(track)
            cmd.expend(["-map", "0:"+sspec,
                        "-metadata:s:"+sspec,
                        "language="+lang_code(lang)])


    outfile = meta.title() + ".mkv"
    cmd.expend([outfile])
    call(cmd)


meta = Metadata("dvd://1")
print(meta._metadata)
print(meta._aid)
print("fr is track:", meta.audio_track_by_lang("fr"))
print("volume title is:", meta.title())

print("========= RIP ==========")
rip(meta)
