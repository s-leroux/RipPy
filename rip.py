import argparse

import re
from itertools import chain
from subprocess import Popen,call,PIPE
from pipes import quote

MPLAYER_GET_METADATA = """mplayer {fname} \\
        -vo null -ao null -frames 0 \\
        -identify """

MPLAYER_DUMP = """mplayer {infile} \\
            -dumpstream -dumpfile \\
            {outfile}"""

FFMPEG = """ffmpeg -i {infile} \\
            """
FFMPEG_VIDEO = """ \\
            -map 0:{sspec} \\
            -codec:{sspec} libx264 \\
            -preset:{sspec} slow \\
            -b:{sspec} 1.5M"""   
FFMPEG_VIDEO_DEINTERLACE = """ \\
            -filter:{sspec} [in]yadif=0:0:0[out]"""
FFMPEG_AUDIO = """ \\
            -map 0:{sspec} \\
            -codec:{sspec} copy \\
            -metadata:s:{sspec} language={lang}"""
FFMPEG_SUBTITLES = FFMPEG_AUDIO

MPLAYER_METADATA_RE = re.compile("ID_(\w+)=(.*)")
MPLAYER_AUDIO_RE = re.compile(
     "audio stream: (\d+) format: (.+) language: (\w+) aid: (\d+).")
MPLAYER_SUBTITLES_RE = re.compile(
     "subtitle \( sid \): (\d+) language: (\w+)")

dry_run = False
def call_it(cmd):
    if dry_run:
        print(cmd)
    else:
        call(cmd,shell=True) # !!! this assume proper argument escaping !!!

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
        self._sid = {}
        self._out_format = 'mkv'
        self.f_title = title_from_metadata
        self.f_year = constantly(None)
        self.f_interlaced = constantly(False) # There is probable an heuristic

        cmd = MPLAYER_GET_METADATA.format(fname= quote(fName))

        proc = Popen(cmd,
                     stdout = PIPE,
                     shell=True, ### !!! This assume proper argument escaping
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
                self._aid[lang] = idx
                continue

            match = MPLAYER_SUBTITLES_RE.match(line)
            if match:
                idx, lang = match.groups()
                self._sid[lang] = idx
                continue

            print("OUT:",line.strip())


    def subtitles_by_lang(self, lang):
        return self._sid.get(lang)

    def audio_track_by_lang(self, lang):
        return self._aid.get(lang)

    def audio_tracks(self):
        return self._aid

    def title(self):
        return self.f_title(self)

    def year(self):
        return self.f_year(self)

    def interlaced(self):
        return self.f_interlaced(self)

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

    call_it(MPLAYER_DUMP.format(infile = quote(infile),
                                outfile = quote(outfile)))

    return outfile

def lang_code(XX):
    return {
        "fr": "fra",
        "en": "eng",
    }.get(XX, "")

def conv(meta, infile):
    outfile = meta.name() + ".mkv"
    cmd = FFMPEG.format(infile=quote(infile))

    cmd += FFMPEG_VIDEO.format(sspec = "v:0")
    if meta.interlaced():
        cmd += FFMPEG_VIDEO_DEINTERLACE.format(sspec = "v:0")

    for lang in ('fr', 'en'):
        track = meta.audio_track_by_lang(lang)
        if track is not None:
            cmd += FFMPEG_AUDIO.format(sspec = "a:"+str(track),
                                        lang = lang_code(lang))

    for lang in ('fr', 'en'):
        track = meta.subtitles_by_lang(lang)
        if track is not None:
            cmd += FFMPEG_SUBTITLES.format(sspec = "s:"+str(track),
                                        lang = lang_code(lang))
    call_it(" ".join((cmd, quote(outfile))))

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
    parser.add_argument("--interlaced",
                            help="Mark the video as being interlaced",
                            action='store_true',
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
    if args.interlaced is not None:
        meta.f_interlaced = constantly(args.interlaced)

    actions = []
    if not args.no_dump:
        actions.append(dump)
    if not args.no_conv:
        actions.append(conv)

    infile = meta._fName
    for action in actions:
        infile = action(meta, infile)

    print("Final file:", infile)


