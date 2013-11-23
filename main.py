import argparse

import re
import os, os.path
from itertools import chain
from subprocess import Popen,call,PIPE
from pipes import quote
from io import StringIO
from rip import pred


MPLAYER_GET_METADATA = """mplayer {fname} \\
        -dvd-device {dvd} \\
        -vo null -ao null -frames 0 \\
        -identify """

MPLAYER_DUMP = """mplayer {infile} \\
        -dvd-device {dvd} \\
            -dumpstream -dumpfile \\
            {outfile}"""

FFPROBE_STREAM_INFO = """ffprobe \\
            -probesize {psize} -analyzeduration {aduration} \\
            -show_format -show_streams \\
            -of csv \\
            -show_entries 'stream=index,codec_type,id' \\
            -i {fname}"""

FFMPEG = """ffmpeg -y  \\
            -probesize {psize} -analyzeduration {aduration} \\
            -i {infile}"""
FFMPEG_VIDEO = """ \\
            -map 0:{ispec} \\
            -codec:{ospec} libx264 \\
            -preset:{ospec} slow \\
            -tune:{ospec} {tune} \\
            -crf:{ospec} 20"""
FFMPEG_VIDEO_DEINTERLACE = """ \\
            -filter:{ospec} [in]yadif=0:0:0[out]"""
FFMPEG_AUDIO = """ \\
            -map 0:{ispec} \\
            -codec:{ospec} copy \\
            -metadata:s:{ospec} language={lang}"""
FFMPEG_SUBTITLES = FFMPEG_AUDIO

MKVPROPEDIT="""mkvpropedit {fname} """
MKVPROPEDIT_INFO=""" \\
                    --edit info --set {key}={value}"""
MKVPROPEDIT_TRACK=""" \\
                    --edit track:{st_type}{st_out_idx} --set {key}={value}"""
MKVPROPEDIT_CHAPTERS=""" \\
                    --chapters {chapfile}"""

MPLAYER_METADATA_RE = re.compile("ID_(\w+)=(.*)")
MPLAYER_VIDEO_RE = re.compile(
     "ID_VIDEO_ID=(\d+)")
MPLAYER_AUDIO_RE = re.compile(
     "audio stream: (\d+) format: (.+) language: (\w+) aid: (\d+).")
MPLAYER_SUBTITLES_RE = re.compile(
     "subtitle \( sid \): (\d+) language: (\w+)")
MPLAYER_CHAPTERS_RE = re.compile(
     "CHAPTERS: ((\d\d:\d\d:\d\d.\d\d\d,)*)")

dry_run = False
def call_it(cmd):
    if dry_run:
        print(cmd)
    else:
        print("RUNNING:")
        print(cmd)
        call(cmd,shell=True) # !!! this assume proper argument escaping !!!

def volume_from_metadata(self):
    """Returns the disk title (based on DVD_VOLUME_ID)
    """
    vid = self._metadata["DVD_VOLUME_ID"]
    volume = vid if vid else "NO_NAME"
    return volume.replace('_',' ').title()

def title_from_volume(self):
    return self.volume()

def duration_from_probesize(self):
    return self.probesize()//2

def constantly(value):
    """Generate a fuction the returns a constant value
    """
    def _const(*args, **kwargs):
        return value

    return _const

import rip.db

class Metadata:
    def __init__(self, fName):
        self._fName = fName
        self._metadata = {}
        self._out_format = 'mkv'
        self._lcodes = ( 'fr', 'en' )
        self._streams = rip.db.DB()
        self._chapters=set()
        self.f_volume = volume_from_metadata
        self.f_title = title_from_volume
        self.f_year = constantly(None)
        self.f_episode = constantly(None)
        self.f_interlaced = constantly(False) # There is probable an heuristic
        self.f_probesize = constantly(5)
        self.f_analyzeduration = duration_from_probesize

    def init(self):
        cmd = MPLAYER_GET_METADATA.format(fname=quote(self._fName),dvd=quote(self._dvd))

        proc = Popen(cmd,
                     stdout = PIPE,
                     shell=True, ### !!! This assume proper argument escaping
                     universal_newlines = True)
        for line in proc.stdout:
            match = MPLAYER_METADATA_RE.match(line)
            if match:
                key, value = match.group(1,2)
                self._metadata[key] = value
                # continue

            match = MPLAYER_VIDEO_RE.match(line)
            if match:
                idx = match.groups()
                self._streams.append(st_type='v',
                                     st_in_idx=idx)
                continue

            match = MPLAYER_CHAPTERS_RE.match(line)
            if match:
                chapters = match.group(1)[:-1].split(',')

                self._chapters = self._chapters.union(chapters)
                continue

            match = MPLAYER_AUDIO_RE.match(line)
            if match:
                idx, fmt, lang, aid = match.groups()
                self._streams.append(st_type='a',
                                     st_lang=lang,
                                    # st_in_idx=idx, # <-- not a good idea
                                    # to store "streeam index" from
                                    # mplayer
                                     st_id=int(aid))
                continue

            match = MPLAYER_SUBTITLES_RE.match(line)
            if match:
                sid, lang = match.groups()
                self._streams.append(st_type='s',
                                     st_lang=lang,
                                     st_id=0x20+int(sid))
                continue

            print("OUT:",line.strip())


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

    def probesize(self):
        return self.f_probesize(self)

    def analyzeduration(self):
        return self.f_analyzeduration(self)

    def name(self):
        """returns the movie base name either as a single
        file name or a path, depending on the various options
        set.

        If volume is set to something different than title
        or there is an episode number, force subdir.

        Use flat file name otherwise.
        """
        volume = self.volume()
        title = self.title()
        episode = self.episode()
        year = self.year()

        has_subdir = (volume != title) or (episode is not None)

        if has_subdir:
            if year is not None:
                volume = "{} ({})".format(volume, year)
            if episode is not None:
                title = "{}.{}".format(title,episode)

            fmt="{volume}/{title}"
        else:
            if year is not None:
                title = "{} ({})".format(title, year)

            fmt="{title}"

        return fmt.format(volume=volume.replace('/','-'),
                          title=title.replace('/','-'))

    def chapters(self):
        return sorted(self._chapters)

def makeBaseDir(filePath):
    dirs = os.path.dirname(filePath)
    try:
        os.makedirs(dirs)
    except OSError:
        # ignore (assuming we the leaf directory already exists)
        # if this is *not* the real issue, later function will fail
        # anyway
        pass

def dump(meta, infile):
    outfile = meta.name() + ".vob"
    makeBaseDir(outfile)

    if meta._force_dump or not os.path.exists(outfile):
        call_it(MPLAYER_DUMP.format(infile = quote(infile),
                                    outfile = quote(outfile),
                                    dvd=quote(meta._dvd)))

    return outfile

def iso639_1_to_iso639_2(XX):
    return {
        'aa': 'aar', # Afar
        'ab': 'abk', # Abkhazian
        'ae': 'ave', # Avestan
        'af': 'afr', # Afrikaans
        'ak': 'aka', # Akan
        'am': 'amh', # Amharic
        'an': 'arg', # Aragonese
        'ar': 'ara', # Arabic
        'as': 'asm', # Assamese
        'av': 'ava', # Avaric
        'ay': 'aym', # Aymara
        'az': 'aze', # Azerbaijani
        'ba': 'bak', # Bashkir
        'be': 'bel', # Belarusian
        'bg': 'bul', # Bulgarian
        'bh': 'bih', # Bihari languages
        'bi': 'bis', # Bislama
        'bm': 'bam', # Bambara
        'bn': 'ben', # Bengali
        'bo': 'tib', # Tibetan
        'br': 'bre', # Breton
        'bs': 'bos', # Bosnian
        'ca': 'cat', # Catalan; Valencian
        'ce': 'che', # Chechen
        'ch': 'cha', # Chamorro
        'co': 'cos', # Corsican
        'cr': 'cre', # Cree
        'cs': 'cze', # Czech
        'cu': 'chu', # Church Slavic; Old Slavonic; Church Slavonic; Old Bulgarian; Old Church Slavonic
        'cv': 'chv', # Chuvash
        'cy': 'wel', # Welsh
        'da': 'dan', # Danish
        'de': 'ger', # German
        'dv': 'div', # Divehi; Dhivehi; Maldivian
        'dz': 'dzo', # Dzongkha
        'ee': 'ewe', # Ewe
        'el': 'gre', # Greek, Modern (1453-)
        'en': 'eng', # English
        'eo': 'epo', # Esperanto
        'es': 'spa', # Spanish; Castillan
        'et': 'est', # Estonian
        'eu': 'baq', # Basque
        'fa': 'per', # Persian
        'ff': 'ful', # Fulah
        'fi': 'fin', # Finnish
        'fj': 'fij', # Fijian
        'fo': 'fao', # Faroese
        'fr': 'fre', # French
        'fy': 'fry', # Western Frisian
        'ga': 'gle', # Irish
        'gd': 'gla', # Gaelic; Scottish Gaelic
        'gl': 'glg', # Galician
        'gn': 'grn', # Guarani
        'gu': 'guj', # Gujarati
        'gv': 'glv', # Manx
        'ha': 'hau', # Hausa
        'he': 'heb', # Hebrew
        'hi': 'hin', # Hindi
        'ho': 'hmo', # Hiri Motu
        'hr': 'hrv', # Croatian
        'ht': 'hat', # Haitian; Haitian Creole
        'hu': 'hun', # Hungarian
        'hy': 'arm', # Armenian
        'hz': 'her', # Herero
        'ia': 'ina', # Interlingua (International Auxiliary Language Association)
        'id': 'ind', # Indonesian
        'ie': 'ile', # Interlingue; Occidental
        'ig': 'ibo', # Igbo
        'ii': 'iii', # Sichuan Yi; Nuosu
        'ik': 'ipk', # Inupiaq
        'io': 'ido', # Ido
        'is': 'ice', # Icelandic
        'it': 'ita', # Italian
        'iu': 'iku', # Inuktitut
        'ja': 'jpn', # Japanese
        'jv': 'jav', # Javanese
        'ka': 'geo', # Georgian
        'kg': 'kon', # Kongo
        'ki': 'kik', # Kikuyu; Gikuyu
        'kj': 'kua', # Kuanyama; Kwanyama
        'kk': 'kaz', # Kazakh
        'kl': 'kal', # Kalaallisut; Greenlandic
        'km': 'khm', # Central Khmer
        'kn': 'kan', # Kannada
        'ko': 'kor', # Korean
        'kr': 'kau', # Kanuri
        'ks': 'kas', # Kashmiri
        'ku': 'kur', # Kurdish
        'kv': 'kom', # Komi
        'kw': 'cor', # Cornish
        'ky': 'kir', # Kirghiz; Kyrgyz
        'la': 'lat', # Latin
        'lb': 'ltz', # Luxembourgish; Letzeburgesch
        'lg': 'lug', # Ganda
        'li': 'lim', # Limburgan; Limburger; Limburgish
        'ln': 'lin', # Lingala
        'lo': 'lao', # Lao
        'lt': 'lit', # Lithuanian
        'lu': 'lub', # Luba-Katanga
        'lv': 'lav', # Latvian
        'mg': 'mlg', # Malagasy
        'mh': 'mah', # Marshallese
        'mi': 'mao', # Maori
        'mk': 'mac', # Macedonian
        'ml': 'mal', # Malayalam
        'mn': 'mon', # Mongolian
        'mr': 'mar', # Marathi
        'ms': 'may', # Malay
        'mt': 'mlt', # Maltese
        'my': 'bur', # Burmese
        'na': 'nau', # Nauru
        'nb': 'nob', # Bokmål, Norwegian; Norwegian Bokmål
        'nd': 'nde', # Ndebele, North; North Ndebele
        'ne': 'nep', # Nepali
        'ng': 'ndo', # Ndonga
        'nl': 'dut', # Dutch; Flemish
        'nn': 'nno', # Norwegian Nynorsk; Nynorsk, Norwegian
        'no': 'nor', # Norwegian
        'nr': 'nbl', # Ndebele, South; South Ndebele
        'nv': 'nav', # Navajo; Navaho
        'ny': 'nya', # Chichewa; Chewa; Nyanja
        'oc': 'oci', # Occitan (post 1500)
        'oj': 'oji', # Ojibwa
        'om': 'orm', # Oromo
        'or': 'ori', # Oriya
        'os': 'oss', # Ossetian; Ossetic
        'pa': 'pan', # Panjabi; Punjabi
        'pi': 'pli', # Pali
        'pl': 'pol', # Polish
        'ps': 'pus', # Pushto; Pashto
        'pt': 'por', # Portuguese
        'qu': 'que', # Quechua
        'rm': 'roh', # Romansh
        'rn': 'run', # Rundi
        'ro': 'rum', # Romanian; Moldavian; Moldovan
        'ru': 'rus', # Russian
        'rw': 'kin', # Kinyarwanda
        'sa': 'san', # Sanskrit
        'sc': 'srd', # Sardinian
        'sd': 'snd', # Sindhi
        'se': 'sme', # Northern Sami
        'sg': 'sag', # Sango
        'si': 'sin', # Sinhala; Sinhalese
        'sk': 'slo', # Slovak
        'sl': 'slv', # Slovenian
        'sm': 'smo', # Samoan
        'sn': 'sna', # Shona
        'so': 'som', # Somali
        'sq': 'alb', # Albanian
        'sr': 'srp', # Serbian
        'ss': 'ssw', # Swati
        'st': 'sot', # Sotho, Southern
        'su': 'sun', # Sundanese
        'sv': 'swe', # Swedish
        'sw': 'swa', # Swahili
        'ta': 'tam', # Tamil
        'te': 'tel', # Telugu
        'tg': 'tgk', # Tajik
        'th': 'tha', # Thai
        'ti': 'tir', # Tigrinya
        'tk': 'tuk', # Turkmen
        'tl': 'tgl', # Tagalog
        'tn': 'tsn', # Tswana
        'to': 'ton', # Tonga (Tonga Islands)
        'tr': 'tur', # Turkish
        'ts': 'tso', # Tsonga
        'tt': 'tat', # Tatar
        'tw': 'twi', # Twi
        'ty': 'tah', # Tahitian
        'ug': 'uig', # Uighur; Uyghur
        'uk': 'ukr', # Ukrainian
        'ur': 'urd', # Urdu
        'uz': 'uzb', # Uzbek
        've': 'ven', # Venda
        'vi': 'vie', # Vietnamese
        'vo': 'vol', # Volapük
        'wa': 'wln', # Walloon
        'wo': 'wol', # Wolof
        'xh': 'xho', # Xhosa
        'yi': 'yid', # Yiddish
        'yo': 'yor', # Yoruba
        'za': 'zha', # Zhuang; Chuang
        'zh': 'chi', # Chinese
        'zu': 'zul', # Zulu
    }.get(XX, "")

def probe(meta, infile):
    """Probe a streams and try to match ids with their
    corresponding index
    """
    cmd = FFPROBE_STREAM_INFO.format(fname=quote(infile),
                        psize=meta.probesize() * 1000000,
                        aduration=meta.analyzeduration() * 1000000)

    proc = Popen(cmd,
                 stdout = PIPE,
                 shell=True, ### !!! This assume proper argument escaping
                 universal_newlines = True)
    for line in proc.stdout:
        header, index, codec_type, *tail = fields=line.split(',')
        if header != 'stream':
            continue

        if codec_type == 'audio':
            st_type = 'a'
            st_id = int(tail[0],base=0)
        elif codec_type == 'subtitle':
            st_type = 's'
            st_id = int(tail[0],base=0)
        else:
            continue

        st_in_idx = int(index,base=0)

        print("FOUND stream id {} ({}) as index {}".format(
                     st_id, st_type, st_in_idx))

        stream = meta._streams.get(st_type=st_type,st_id=st_id)
        if stream:
            stream['st_in_idx'] = st_in_idx
        else:
            print("Can't find stream 0x{:02x}".format(st_id))

    print([i for i in meta._streams])

    return infile

def conv(meta, infile):
    title, _ = os.path.splitext(infile)

    outfile = ".".join((title, meta._out_format))
    cmd = FFMPEG.format(infile=quote(infile),
                        psize=meta.probesize() * 1000000,
                        aduration=meta.analyzeduration() * 1000000)

    cmd += FFMPEG_VIDEO.format(ispec="v:0", ospec="v:0", tune=meta._tune)
    meta._streams.get(st_type='v')['st_out_idx'] = 0

    if meta.interlaced():
        cmd += FFMPEG_VIDEO_DEINTERLACE.format(sspec="v:0", ospec="v:0")

    aid = 0
    for stream in meta._streams.all(st_type='a').fltr(pred.order_by('st_lang',
                                            meta._lcodes), pred.having('st_in_idx')):
        stream['st_out_idx'] = aid
        cmd += FFMPEG_AUDIO.format(ispec = quote('#0x{:02x}'.format(stream['st_id'])),
                                       ospec = "a:"+str(aid),
                                       lang = iso639_1_to_iso639_2(stream['st_lang']))
        aid += 1

    sid = 0
    for stream in meta._streams.all(st_type='s').fltr(pred.order_by('st_lang',
                                            meta._lcodes), pred.having('st_in_idx')):
        stream['st_out_idx'] = sid
        cmd += FFMPEG_SUBTITLES.format(ispec = quote('#0x{:02x}'.format(stream['st_id'])),
                                       ospec = "s:"+str(sid),
                                       lang = iso639_1_to_iso639_2(stream['st_lang']))
        sid += 1

    if meta._force_conv or not os.path.exists(outfile):
        call_it(" ".join((cmd, quote(outfile))))

    return outfile

def print_meta(meta, infile):
    print(meta._metadata)
    return infile

def chapters(meta,infile):
    chapfile = meta.name() + ".chp"
    with open(chapfile, "wt") as f:
        for idx, val in enumerate(meta.chapters()):
            print("CHAPTER{:02d}={}".format(idx,val), file=f)
            print("CHAPTER{:02d}NAME=Chapter {}".format(idx,idx), file=f)

    cmd = MKVPROPEDIT.format(fname=quote(infile))
    cmd += MKVPROPEDIT_CHAPTERS.format(chapfile=quote(chapfile))

    call_it(cmd)

    return infile

def set_defaults(meta, infile):
    # XXX should check if this is really a Matroska?
    cmd = MKVPROPEDIT.format(fname=quote(infile))
    cmd += MKVPROPEDIT_INFO.format(key='title', value=quote(meta.title()))

    for stream in meta._streams.all(st_type='s').fltr(pred.having('st_out_idx')):
        cmd += MKVPROPEDIT_TRACK.format(st_type=stream['st_type'],
                                      st_out_idx=stream['st_out_idx']+1,
                                      key='flag-default',
                                      value = '0')

    call_it(cmd)

    return infile


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
    parser.add_argument("--dvd-device",
                            help="Select the dvd device",
                            default='/dev/dvd')
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
    parser.add_argument("--lang",
                            help="Langage code for tracks (audio+subtitles). Default 'fr,en'",
                            default='fr,en')
    parser.add_argument("--tune",
                            help="Tune for a specific media (default film)",
                            default="film")
    parser.add_argument("--interlaced",
                            help="Mark the video as being interlaced",
                            action='store_true',
                            default=None)
    parser.add_argument("--probesize",
                            help="Set the probesize in Mframes (x1000000)",
                            type=int,
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
    parser.add_argument("--force-dump", 
                            help="Force dump (i.e.: copy/rip) even if already done",
                            action='store_true',
                            default=False)
    parser.add_argument("--force-conv", 
                            help="Force re-encoding",
                            action='store_true',
                            default=False)

    args = parser.parse_args()

    print(args)

    meta = Metadata(args.infile)
    meta._dvd = args.dvd_device
    meta._out_format = args.container
    meta._lcodes = args.lang.split(',')
    meta._tune = args.tune
    meta._force_dump = args.force_dump
    meta._force_conv = args.force_conv

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
    if args.probesize is not None:
        meta.f_probesize = constantly(args.probesize)

    meta.init()

    actions = []
    if args.print_meta:
        actions.append(print_meta)
    actions.append(dump)
    actions.append(probe)
    actions.append(conv)
    actions.append(chapters)
    actions.append(set_defaults)

    infile = meta._fName

    for action in actions:
        infile = action(meta, infile)



