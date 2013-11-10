import argparse

import re
import os, os.path
from itertools import chain
from subprocess import Popen,call,PIPE
from pipes import quote
from io import StringIO

SCRIPT_HEADER = """#!/bin/bash
set -e

MPLAYER={mplayer}
FFMPEG={ffmpeg}
                
"""


MPLAYER_GET_METADATA = """mplayer {fname} \\
        -vo null -ao null -frames 0 \\
        -identify """

MPLAYER_DUMP = """$MPLAYER {infile} \\
            -dumpstream -dumpfile \\
            {outfile}"""

FFMPEG = """$FFMPEG -y -i {infile}"""
FFMPEG_VIDEO = """ \\
            -map 0:{ispec} \\
            -codec:{ospec} libx264 \\
            -preset:{ospec} slow \\
            -b:{ospec} 1.5M"""   
FFMPEG_VIDEO_DEINTERLACE = """ \\
            -filter:{ospec} [in]yadif=0:0:0[out]"""
FFMPEG_AUDIO = """ \\
            -map 0:{ispec} \\
            -codec:{ospec} copy \\
            -metadata:s:{ospec} language={lang}"""
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

def volume_from_metadata(self):
    """Returns the disk title (based on DVD_VOLUME_ID)
    """
    vid = self._metadata["DVD_VOLUME_ID"]
    volume = vid if vid else "NO_NAME"
    return volume.replace('_',' ').title()

def title_from_volume(self):
    return self.volume()

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
        self.f_volume = volume_from_metadata
        self.f_title = title_from_volume
        self.f_year = constantly(None)
        self.f_episode = constantly(None)
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

    def volume(self):
        return self.f_volume(self)

    def title(self):
        return self.f_title(self)

    def year(self):
        return self.f_year(self)

    def episode(self):
        return self.f_episode(self)

    def interlaced(self):
        return self.f_interlaced(self)

    def name(self):
        """returns the movie name as a tupple (volume, title)
        based on its volume, title, year and/or episode
        """
        volume = self.volume()
        title = self.title()

        year = self.year()
        if year is not None:
            volume = "{} ({})".format(volume,year)

        episode = self.episode()
        if episode is not None:
            title = "{}.{}".format(title,episode)

        return (volume, title)

def dump(meta, infile, script):
    _, title = meta.name()
    outfile = title.replace('/','-') + ".vob"

    print(MPLAYER_DUMP.format(infile = quote(infile),
                              outfile = quote(outfile)),
          file=script)

    return outfile

def lang_code(XX):
    return {
        "fr": "fra",
        "en": "eng",
    }.get(XX, "")

def conv(meta, infile, script):
    title, _ = os.path.splitext(infile)

    outfile = title + ".mkv"
    cmd = FFMPEG.format(infile=quote(infile))

    cmd += FFMPEG_VIDEO.format(ispec="v:0", ospec="v:0")
    if meta.interlaced():
        cmd += FFMPEG_VIDEO_DEINTERLACE.format(sspec="v:0", ospec="v:0")

    aid = 0
    for lang in ('fr', 'en'):
        track = meta.audio_track_by_lang(lang)
        if track is not None:
            cmd += FFMPEG_AUDIO.format(ispec = "a:"+str(track),
                                       ospec = "a:"+str(aid),
                                       lang = lang_code(lang))
            aid += 1

    sid = 0
    for lang in ('fr', 'en'):
        track = meta.subtitles_by_lang(lang)
        if track is not None:
            cmd += FFMPEG_SUBTITLES.format(ispec = "s:"+str(track),
                                        ospec = "a:"+str(sid),
                                        lang = lang_code(lang))
            sid += 1
    print(" ".join((cmd, quote(outfile))),
          file=script)

    return outfile

def print_meta(meta, infile, script):
    print(meta._metadata)
    return infile

def subdir(meta, infile, script):
    volume, _ = meta.name()

    path = volume.replace('/','-')
    outfile = os.path.join(path, infile)

    print("mkdir -p -- {path} || test -d {path}".format(path=quote(path)),
          file=script)
    print("mv -- {infile} {outfile}".format(infile=quote(infile),
                                            outfile=quote(outfile)),
           file=script)

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
    parser.add_argument("--volume",
                            help="Set the disk volume title",
                            default=None)
    parser.add_argument("--title",
                            help="Set the video title",
                            default=None)
    parser.add_argument("--year",
                            help="Set the video year",
                            default=None)
    parser.add_argument("--episode",
                            help="Set the episode code (2x01 or s2e1)",
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
    # Actions
    parser.add_argument("--print-meta", 
                            help="Print meta-data (for debugging purposes)",
                            action='store_true',
                            default=False)
    parser.add_argument("--subdir", 
                            help="Put the final file in a sub-directory",
                            action='store_true',
                            default=False)
    parser.add_argument("--skip-dump", 
                            help="Don't dump (i.e.: copy/rip) the source file",
                            action='store_const',
                            const='echo mplayer',default='mplayer',
                            dest='mplayer')
    parser.add_argument("--skip-conv", 
                            help="Don't convert (i.e.:re-encode) the video stream",
                            action='store_const',
                            const='echo ffmpeg',default='ffmpeg',
                            dest='ffmpeg')

    args = parser.parse_args()

    print(args)

    meta = Metadata(args.infile)
    meta._out_format = args.container
    if args.volume is not None:
        meta.f_volume = constantly(args.volume)
    if args.title is not None:
        meta.f_title = constantly(args.title)
    if args.year is not None:
        meta.f_year = constantly(args.year)
    if args.episode is not None:
        meta.f_episode = constantly(args.episode)
    if args.interlaced is not None:
        meta.f_interlaced = constantly(args.interlaced)

    actions = []
    if args.print_meta:
        actions.append(print_meta)
    actions.append(dump)
    actions.append(conv)
    if args.subdir:
        actions.append(subdir)

    infile = meta._fName
    script = StringIO()
    print(SCRIPT_HEADER.format(ffmpeg = quote(args.ffmpeg),
                               mplayer = quote(args.mplayer)),
          file=script)

    for action in actions:
        infile = action(meta, infile, script)


    if args.dry:
        print(script.getvalue())
    else:
        call(script.getvalue(),shell=True)


