import argparse

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

dry_run = False
def call_it(cmd):
    if dry_run:
        print(" ".join(cmd))
    else:
        call(cmd)

def title_from_metadata(self):
    """Returns the disk title (based on DVD_VOLUME_ID)
    """
    vid = self._metadata["DVD_VOLUME_ID"]
    vtitle = vid if vid else "NO_NAME"
    return vtitle.replace('_',' ').title()

def constantly(value):
    """Generate a fuction the returns a constant value
    """
    def _const(*args, **kwargs):
        return value

    return _const

class Metadata:
    def __init__(self, fName):
        self._fName = fName
        self._metadata = {}
        self._aid = {}
        self._out_format = 'mkv'
        self.f_title = title_from_metadata
        self.f_year = constantly(None)

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

        # Post-precessing metadata

                

    def audio_track_by_lang(self, lang):
        for idx, l in self._aid.items():
            if lang == l:
                return idx

        return None

    def audio_tracks(self):
        return self._aid

    def title(self):
        return self.f_title(self)

    def year(self):
        return self.f_year(self)

    def name(self):
        """returns the movie name based on this title and year
        """
        name = self.title()
        year = self.year()
        if year is not None:
            name = "{} ({})".format(name,year)

        return name

def dump(meta, infile):
    outfile = meta.name() + ".vob"

    cmd = ["mplayer",
            infile,
            "-dumpstream", "-dumpfile",
            outfile]

    call_it(cmd)
    return outfile

def lang_code(XX):
    return {
        "fr": "fra",
        "en": "eng",
    }.get(XX, "")

def conv(meta, infile):
    outfile = meta.name() + ".mkv"
    cmd = ["avconv",
            "-i", infile,
            "-codec:v", "libx264", 
            "-pre", "slow", 
            "-b:v", "1.5M", 
            "-map", "0:v",
            "-codec:a", "copy"]
    for lang in ('fr', 'en'):
        track = meta.audio_track_by_lang(lang)
        if track is not None:
            sspec = "a:"+str(track)
            cmd.extend(["-map", "0:"+sspec,
                        "-metadata:s:"+sspec,
                        "language="+lang_code(lang)])


    outfile = meta.name() + ".mkv"
    cmd.extend([outfile])
    call_it(cmd)

    return outfile


#print(meta._metadata)
#print(meta._aid)
#print("fr is track:", meta.audio_track_by_lang("fr"))
#print("volume title is:", meta.title())

# print("========= RIP ==========")
# rip(meta)

#print("======== CONV ==========")
#conv(meta)

#
# Main program
#
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("infile", 
                            help="The video source to rip",
                            nargs='?',
                            default="dvd://1")
    parser.add_argument("--title",
                            help="Set the video title",
                            default=None)
    parser.add_argument("--year",
                            help="Set the video year",
                            default=None)
    parser.add_argument("--container",
                            help="Set the container format (default mkv)",
                            default='mkv')
    parser.add_argument("--dry", 
                            help="Show the commands that would be executed",
                            action='store_true',
                            default=False)
    parser.add_argument("--no-dump", 
                            help="Don't dump (i.e.: copy/rip) the source file",
                            action='store_true',
                            default=False)
    parser.add_argument("--no-conv", 
                            help="Don't convert (i.e.:re-encode) the video stream",
                            action='store_true',
                            default=False)

    args = parser.parse_args()
    dry_run = args.dry

    print(args)

    meta = Metadata(args.infile)
    meta._out_format = args.container
    if args.title is not None:
        meta.f_title = constantly(args.title)
    if args.year is not None:
        meta.f_year = constantly(args.year)

    actions = []
    if not args.no_dump:
        actions.append(dump)
    if not args.no_conv:
        actions.append(conv)

    infile = meta._fName
    for action in actions:
        infile = action(meta, infile)

    print("Final file:", infile)


