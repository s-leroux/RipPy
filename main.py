import argparse

import re
import math
import os, os.path
import shutil
from itertools import chain, product, zip_longest
from subprocess import Popen,call,PIPE
from pipes import quote
from io import StringIO, TextIOWrapper
from rip import pred

MPLAYER_GET_METADATA = """mplayer {fname} \\
        -dvd-device {dvd} \\
        -vo null -ao null -frames 0 \\
        -identify """

MPLAYER_DUMP = """mplayer {infile} \\
            -dumpstream -dumpfile {outfile}"""

MPLAYER_DVD_DUMP = """mplayer {infile} \\
            -dvd-device {dvd} \\
            -chapter {chapter}-{chapter} \\
            -dumpstream -dumpfile {outfile}"""

MPLAYER_DVD_DUMP_CHAPTER = MPLAYER_DVD_DUMP + """ \\
            -dvd-device {dvd}"""

FFPROBE_TS = """ffprobe \\
            -probesize {psize} -analyzeduration {aduration} \\
            -show_streams \\
            -i file:{fname}"""

FFPROBE_STREAM_INFO = """ffprobe \\
            -probesize {psize} -analyzeduration {aduration} \\
            -show_format -show_streams \\
            -of csv \\
            -show_entries 'stream=index,codec_type,id' \\
            -i file:{fname}"""

FFMPEG_IDET = """ffmpeg -nostdin -filter:v idet -frames:v 20000 -an \\
            -f rawvideo -y /dev/null -ss {ss} \\
            -i file:{fname} \\
            2>&1 | grep TFF"""

FFMPEG = """ffmpeg -nostdin -y \\
            -probesize {psize} -analyzeduration {aduration} \\
            {ff} \\
            -fix_sub_duration \\
            -i file:{infile} -ss {ss}"""
FFMPEG_VIDEO = """ \\
            -map 0:{ispec} \\
            -codec:{ospec} {videoformat} \\
            -preset:{ospec} slow \\
            -tune:{ospec} {tune} \\
            -crf:{ospec} 20"""
FFMPEG_VIDEO_DEINTERLACE = """ \\
            -filter:{ospec} [in]yadif=0:0:0[out]"""
FFMPEG_VIDEO_ASPECT = """ \\
            -aspect:{ospec} {ratio}"""
FFMPEG_VIDEO_CROP = """ \\
            -filter:{ospec} 'crop={crop}'"""
FFMPEG_AUDIO = """ \\
            -map 0:{ispec} \\
            -codec:{ospec} {audioformat} \\
            -metadata:s:{ospec} language={lang}"""
FFMPEG_SUBTITLES = """ \\
            -map 0:{ispec} \\
            -codec:{ospec} {subformat} \\
            -metadata:s:{ospec} language={lang}"""
#FFMPEG_OUTFILE=""" \\
#            -reserve_index_space {idx_space} \\
#            {outfile}"""
FFMPEG_OUTFILE=""" \\
            file:{outfile}"""

FFMPEG_FINAL_COPY = """ ffmpeg -nostdin -y -i file:{infile} \\
            -map 0 -codec copy \\
            file:{outfile}"""

MKVPROPEDIT="""mkvpropedit {fname} """
MKVPROPEDIT_INFO=""" \\
                 --edit info --set {key}={value}"""
                 # ^^^ XXX this *sometimes* leads to
                 # mkv file unreadable by ffmpeg... 
MKVPROPEDIT_TRACK=""" \\
                    --edit track:{st_type}{st_out_idx} --set {key}={value}"""
MKVPROPEDIT_CHAPTERS=""" \\
                    --chapters {chapfile}"""

MKVMERGE="""mkvmerge -o {dst} {src}"""

FFMPEG_IDET_RE = re.compile(".*TFF:\s*(\d+)\s*BFF:\s*(\d+)\s*Progressive:\s*(\d+)\s*Undetermined:\s*(\d+)\s*""")
MPLAYER_METADATA_RE = re.compile("ID_(\w+)=(.*)")
MPLAYER_VIDEO_RE = re.compile(
     "ID_VIDEO_ID=(\d+)")
MPLAYER_AUDIO_RE = re.compile(
     "audio stream: (\d+) format: (.+) language: (\w+) aid: (\d+).")
MPLAYER_SUBTITLES_RE = re.compile(
     "subtitle \( sid \): (\d+) language: (\w+)")
MPLAYER_CHAPTERS_RE = re.compile(
     "CHAPTERS: ((\d\d:\d\d:\d\d.\d\d\d,)*)")

NUKE_EXTRACT_VIDEO="""mencoder -vid 0 -nosound -ovc copy -of mpeg {infile} -o {outfile}"""
NUKE_EXTRACT_AUDIO="""mencoder -aid {st_id} -ovc raw -oac copy -of rawaudio {infile} -o {outfile}"""
NUKE_EXTRACT_ST="""ffmpeg -nostdin -y -i {infile} -codec:s -vn -an copy -map 0:'#{st_id}?' {outfile}"""

def zip_repeat(a, b):
    olda = oldb = None
    for ita, itb in zip_longest(a,b):
        if ita:
            olda = ita
        if itb:
            oldb = itb
        yield (olda, oldb)
        

dry_run = False
def call_it(cmd):
    if dry_run:
        print(cmd)
        return 0
    else:
        print("RUNNING:")
        print(cmd)
        status = call(cmd,shell=True) # !!! this assume proper argument escaping !!!
        if status:
            print("NON-NUL EXIT STATUS: "+str(status))
            print("WHILE RUNNING:")
            print(cmd)

        return status

def rm(filePath):
    print("REMOVING {f}".format(f=filePath))
    return os.unlink(filePath)

def volume_from_metadata(self):
    """Returns the disk title (based on DVD_VOLUME_ID)
    """
    vid = self._metadata["DVD_VOLUME_ID"]
    volume = vid if vid else "NO_NAME"
    return volume.replace('_',' ').title()

def title_from_volume(self):
    return self.volume()

def duration_from_metadata(self):
    return float(self._metadata["LENGTH"])

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
        self._lcodes = ( 'fr', 'en', 'unknown', 'xx', 'qaa', 'qad' )
        self._scodes = ( 'fr', 'en', 'unknown', 'xx', 'qaa', 'qad' )
        self._streams = rip.db.DB()
        self._chapters=set()

        self._subformat = "copy"
        self._audioformat = "copy"
        self._videoformat = "libx264"

        self.f_volume = volume_from_metadata
        self.f_title = title_from_volume
        self.f_year = constantly(None)
        self.f_episode = constantly(None)
        self.f_interlaced = constantly(False) # There is probable an heuristic
        self.f_aspect_ratio = constantly(None)
        self.f_crop = constantly(None)
        self.f_probesize = constantly(2000)
        self.f_idxsize = constantly(50*1024)
        self.f_analyzeduration = duration_from_probesize
        self.f_duration = duration_from_metadata

    def initFromDVD(self):
        # self.subformat = "copy" # prevent dvdsub -> dvdsub
        self._subformat = "dvdsub" # prevent dvdsub -> dvdsub

        for part in [p.strip() for p in self._fName.split("+")]:
            cmd = MPLAYER_GET_METADATA.format(fname=quote(part),dvd=quote(self._dvd[-1]))

            proc = Popen(cmd,
                         stdout = PIPE,
                         shell=True) ### !!! This assume proper argument escaping
            stdout = TextIOWrapper(proc.stdout,errors='ignore')
            for line in stdout:
                match = MPLAYER_METADATA_RE.match(line)
                if match:
                    key, value = match.group(1,2)
                    self._metadata[key] = value
                    # continue

                # At this point, we don't have access to the stream id
                match = MPLAYER_VIDEO_RE.match(line)
                if match:
                    idx,  = match.groups()
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

                print("OUT({}):".format(part),line.strip())

    def initFromTS(self):
        cmd = FFPROBE_TS.format(fname=quote(self._fName),
                        psize=meta.probesize() * 1000000,
                        aduration=meta.analyzeduration() * 1000000)

        proc = Popen(cmd,
                     stdout = PIPE,
                     shell=True) ### !!! This assume proper argument escaping
        stdout = TextIOWrapper(proc.stdout,errors='ignore')

        kv_re = re.compile("(DISPOSITION:|TAG:)?(.*)=(.*)")
        kv = {}

        for line in stdout:
            match = kv_re.match(line)
            if match:
                key, value = match.group(2,3)
                kv[key] = value
                # continue
            elif line.strip() == '[/STREAM]':
                idx = int(kv['index'])
                t = 'v' if kv['codec_type'] == 'video' \
                    else 'a' if kv['codec_type'] == 'audio' \
                    else 's' if kv['codec_type'] == 'subtitle' \
                    else '?'

                d = {'st_type': t, 'st_in_idx': idx, 'st_id': int(kv['id'],base=0), 'st_found': True}
                if t == 'a':
                    d['aid'] = int(kv['id'],base=0)

                l = kv.get('language')
                if l is not None:
                    d['st_lang'] = iso639_2_to_iso639_1(l)

                self._streams.append(**d)

                if 'duration' in kv:
                    try:
                        self._metadata['LENGTH'] = float(kv['duration'])
                    except:
                        pass

        print([i for i in meta._streams])


    def volume(self):
        return self.f_volume(self)

    def title(self):
        return self.f_title(self)

    def year(self):
        return self.f_year(self)

    def duration(self):
        return self.f_duration(self)

    def episode(self):
        return self.f_episode(self)

    def interlaced(self):
        return self.f_interlaced(self)

    def crop(self):
        return self.f_crop(self)

    def aspect_ratio(self):
        return self.f_aspect_ratio(self)

    def probesize(self):
        return self.f_probesize(self)

    def idxsize(self):
        return self.f_idxsize(self)

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
            if episode is not None:
                title = "{}.{}.{}".format(volume,episode,title)
            if year is not None:
                volume = "{} ({})".format(volume, year)

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
    # if infile contains '+', it is assumed to be a multi-part
    # dump.
    # As an example: dvd://1+dvd://2

    outfile = meta.name() + ".vob"
    makeBaseDir(outfile)

    reallyDump = not os.path.exists(outfile)
    try:
        if meta._force_dump:
            os.unlink()
            reallyDump = true
    except FileNotFoundError:
        reallyDump = true

    if reallyDump:
        i = 0

        parts = (p.strip() for p in infile.split("+"))
        for dvd, part in zip_repeat(meta._dvd, parts):
            chapter = ""
            partfile = outfile+".{}".format(i)
            print("DUMP",part,"TO",partfile)

            if part.startswith("dvd://"):
                part, sep, chapter = part.partition('#')
                if chapter == "":
                    DUMP = MPLAYER_DVD_DUMP
                else:
                    DUMP = MPLAYER_DVD_DUMP_CHAPTER
            else:
                chapter = None
                DUMP = MPLAYER_DUMP

            call_it(DUMP.format(infile = quote(part),
                                        outfile = quote(partfile),
                                        chapter = quote(chapter),
                                        dvd=quote(dvd)))
            
            if i == 0:
                os.rename(partfile,outfile)
            else:
                with open(outfile, "ab") as out:
                    shutil.copyfileobj(open(partfile, "rb"), out)
                os.unlink(partfile)
            i += 1


    return outfile

iso639_1_to_iso639_2_map = {
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
    }
iso639_2_to_iso639_1_map = dict((value,key) for key,value in iso639_1_to_iso639_2_map.items())
# non standard codes
iso639_2_to_iso639_1_map['fra'] = 'fr'

def iso639_1_to_iso639_2(XX):
    return iso639_1_to_iso639_2_map.get(XX, XX)

def iso639_2_to_iso639_1(XXX):
    return iso639_2_to_iso639_1_map.get(XXX, XXX)

def probe(meta, infile):
    """Probe a streams and try to match ids with their
    corresponding index
    """
    cmd = FFPROBE_STREAM_INFO.format(fname=quote(infile),
                        psize=meta.probesize() * 1000000,
                        aduration=meta.analyzeduration() * 1000000)

    print("PROBE CMD IS",cmd)
    proc = Popen(cmd,
                 stdout = PIPE,
                 shell=True) ### !!! This assume proper argument escaping
    stdout = TextIOWrapper(proc.stdout,errors='ignore')
    for line in stdout:
        print("PROBE:",line)
        header, index, codec_type, *tail = fields=line.split(',')
        if header != 'stream':
            continue

        if codec_type == 'audio':
            st_type = 'a'
            st_id = int(tail[0],base=0)
        elif codec_type == 'subtitle':
            st_type = 's'
            st_id = int(tail[0],base=0)
        elif codec_type == 'video':
            st_type = 'v'
            st_id = int(tail[0],base=0)
        else:
            continue

        st_in_idx = int(index,base=0)

        print("FOUND stream id {} ({}) as index {}".format(
                     st_id, st_type, st_in_idx))

        stream = meta._streams.get(st_type=st_type,st_id=st_id)

        # The video stream is a special case as we don't have its stream ID
        # Assume there is only one vidoe stream
        if not stream and st_type=='v':
            stream = meta._streams.get(st_type='v')

        if not stream:
            print("Append missing stream 0x{:02x}".format(st_id))
            meta._streams.append(st_type=st_type, st_id=st_id, st_lang="unknown",st_in_idx=st_in_idx,st_found=True)
        else:
            stream['st_in_idx'] = st_in_idx
            stream['st_found'] = True
            if 'st_id' not in stream:
                stream['st_id'] = st_id
            if stream['st_id'] != st_id:
                abort("Stream id mismatch: " + str(st_id) + str(stream))

    print([i for i in meta._streams])

    return infile

def abort(message):
    print(message)
    exit(1)

from rip import ffmpeg
def nuke(meta, infile):
    # Extract each stream into its own file
    files = []
    for stream in meta._streams.all(st_found=True):
        print(stream)
        st_id = stream['st_id']
        st_type = stream['st_type']
        
        ext = "m4v" if st_type=='v' else "mp4"
        fname = ".".join((meta.name(),str(st_id),ext))
        files.append(fname)
        stream['st_fname'] = fname
        
        if st_type == 'v':
            cmd = NUKE_EXTRACT_VIDEO.format(infile=quote(infile), outfile=quote(fname))
        elif st_type == 'a':
            cmd = NUKE_EXTRACT_AUDIO.format(infile=quote(infile), st_id=st_id, outfile=quote(fname))
        elif st_type == 's':
            cmd = NUKE_EXTRACT_ST.format(infile=quote(infile), st_id=st_id, outfile=quote(fname))
        else:
            abort("I don't know how to handle stream " + str(stream))

        #print(cmd)
        if call_it(cmd):
            stream['st_found'] = False

    # Recombine streams
    outputFileName = ".".join((meta.name(),"out","mp4"))
    streams_by_index = meta._streams.all(st_found=True).sort(lambda item : item['st_in_idx']).as_list()
    cmd = ffmpeg.new()
    output = cmd.setOutput(outputFileName)
    inputFileNum = 0
    outputStreamIndex = 0

    for stream in streams_by_index:
        input = cmd.newInput(stream['st_fname'])
        output["opts"].append(("-map", '{:d}'.format(inputFileNum)))
        output["opts"].append(("-map_metadata", '{:d}:s'.format(inputFileNum)))
        output["opts"].append(("-metadata:s:{:d}".format(outputStreamIndex), "language={}".format(stream['st_lang'])))
        output["opts"].append(("-streamid", '{:d}:0x{:02x}'.format(outputStreamIndex, stream['st_id'])))
        inputFileNum += 1
        outputStreamIndex += 1

    output["opts"].append(("-c:v", "copy"))
    output["opts"].append(("-c:a", "copy"))
    output["opts"].append(("-c:s", "copy"))

    call_it(cmd.cmd())

    for file in files:
      rm(file)

    return outputFileName

def idet(meta, infile):
    print("Testing if interlaced")
    cmd = FFMPEG_IDET.format(fname=quote(infile),ss=quote(meta._ss))

    iframes, pframes = (0,0)

    print("IDET CMD IS",cmd)
    proc = Popen(cmd,
                 stdout = PIPE,
                 shell=True) ### !!! This assume proper argument escaping
    stdout = TextIOWrapper(proc.stdout,errors='ignore')
    for line in stdout:
        match = FFMPEG_IDET_RE.match(line)
        print(line)
        if match:
            tff, bff, progressive, undetermined = \
                match.groups()

            print(tff,bff,progressive,undetermined,match.groups())

            iframes += int(tff)
            iframes += int(bff)
            pframes += int(progressive)

    print("Score: iframe =",iframes,"pframes =",pframes)
    if iframes > pframes:
        print("*** Interlaced according to idet")
        meta.f_interlaced = constantly(True)
    else:
        print("*** Probably progressive")

    return infile

def conv(meta, infile):
    title, _ = os.path.splitext(infile)

    outfile = ".".join((meta.name(),meta._out_format))
    makeBaseDir(outfile)

    #
    # estimate index (cues) size
    # Routhly 50kB per hour
    #
    hours = math.ceil(meta.duration()/3600)
    idx_space = hours*meta.idxsize()

    print("Duration less than", hours, "hours; idx_space =", idx_space)

    cmd = FFMPEG.format(infile=quote(infile),
                        psize=meta.probesize() * 1000000,
                        aduration=meta.analyzeduration() * 1000000,
                        idx_space=idx_space,
                        ss=quote(meta._ss),
                        ff=meta._ff)
    if meta._to:
        cmd += " -to {to} ".format(to=quote(meta._to))

    cmd += FFMPEG_VIDEO.format(ispec="v:0", ospec="v:0", tune=meta._tune,
            videoformat=meta._videoformat)
    meta._streams.get(st_type='v')['st_out_idx'] = 0

    if meta.interlaced():
        cmd += FFMPEG_VIDEO_DEINTERLACE.format(sspec="v:0", ospec="v:0")

    if meta.aspect_ratio():
        cmd += FFMPEG_VIDEO_ASPECT.format(sspec="v:0", ospec="v:0",
                                                ratio=meta.aspect_ratio())

    if meta.crop():
        cmd += FFMPEG_VIDEO_CROP.format(sspec="v:0", ospec="v:0",
                                                crop=meta.crop())

    aid = 0
    for stream in meta._streams.all(st_type='a').fltr(pred.order_by('st_lang',
                                            meta._lcodes), pred.having('st_in_idx')):
        if stream['st_id'] not in meta._kid:
            stream['st_out_idx'] = aid
            cmd += FFMPEG_AUDIO.format(ispec = quote('#0x{:02x}'.format(stream['st_id'])),
                                           ospec = "a:"+str(aid),
                                           lang = iso639_1_to_iso639_2(stream['st_lang']),
                                           audioformat=meta._audioformat)
            aid += 1

    sid = 0
    for stream in meta._streams.all(st_type='s').fltr(pred.order_by('st_lang',
                                            meta._scodes), pred.having('st_in_idx')):
        if stream['st_id'] not in meta._kid:
            stream['st_out_idx'] = sid
            cmd += FFMPEG_SUBTITLES.format(ispec = quote('#0x{:02x}'.format(stream['st_id'])),
                                           ospec = "s:"+str(sid),
                                           lang = iso639_1_to_iso639_2(stream['st_lang']),
                                           subformat=meta._subformat)
            sid += 1

    cmd += FFMPEG_OUTFILE.format(outfile=quote(outfile),
                                idx_space=idx_space)

    if meta._force_conv or not os.path.exists(outfile):
        if call_it(cmd) != 0:
            print("CONVERSION FAILED --- will use {f}".format(f=infile))
            print("REMOVING {f}".format(f=outfile))
            os.unlink(outfile)
            outfile = infile

    return outfile

def print_meta(meta, infile):
    print(meta._metadata)
    return infile

def chapters(meta,infile):
    if not infile.endswith(".mkv"):
        return infile

    chapfile = meta.name() + ".chp"
    makeBaseDir(chapfile)

    if not os.path.exists(chapfile):
        with open(chapfile, "wt") as f:
            for idx, val in enumerate(meta.chapters()):
                print("CHAPTER{:02d}={}".format(idx,val), file=f)
                print("CHAPTER{:02d}NAME=Chapter {}".format(idx,idx), file=f)

    cmd = MKVPROPEDIT.format(fname=quote(infile))
    cmd += MKVPROPEDIT_CHAPTERS.format(chapfile=quote(chapfile))

    call_it(cmd)

    return infile

def set_defaults(meta, infile):
    if not infile.endswith(".mkv"):
        return infile

    cmd = MKVPROPEDIT.format(fname=quote(infile))
    for stream in meta._streams.all(st_type='s').fltr(pred.having('st_out_idx')):
        cmd += MKVPROPEDIT_TRACK.format(st_type=stream['st_type'],
                                      st_out_idx=stream['st_out_idx']+1,
                                      key='flag-default',
                                      value = '0')

    call_it(cmd)

    # Curiously (?) editing both the segment title and 
    # subtitles default flags in a single call to 
    # mkvpropedit leads to MKV files unreadable by ffmpeg.
    #
    # In addition, they seems to have been called in that
    # precise order: chapters, default flags, segment title
    cmd = MKVPROPEDIT.format(fname=quote(infile))
    cmd += MKVPROPEDIT_INFO.format(key='title', value=quote(meta.title()))

    call_it(cmd)

    return infile

def final_copy(meta, infile):
    if not infile.endswith(".mkv"):
        return infile

    #
    # Some software are unable to understand MKV files whose
    # stream header have been pushed to the end by `mkvpropedit`
    #
    # We will use ffmpeg to remux the file to a less complex
    # format
    #
    title, ext = os.path.splitext(infile)
    outfile = ".".join((title,"DVDRip",ext[1:]))
    cmd = FFMPEG_FINAL_COPY.format(infile=quote(infile),
                                   outfile=quote(outfile))

    call_it(cmd)

    return outfile

def install(meta, infile):
    if meta._target is not None:
        dst = os.path.join(meta._target, infile)
        makeBaseDir(dst)
        print("COPYING {f} to {d}".format(f=infile, d=dst))
        shutil.copy2(infile, dst)
        if not infile.endswith(".vob"):
            print("REMOVING {f}".format(f=infile))
            os.unlink(infile)

    return infile

def clean_vob(meta,infile):
    title, _ = os.path.splitext(infile)
    vob = ".".join((title,"vob"))
    print("REMOVING {f}".format(f=vob))
    os.unlink(vob)

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
    import sys; print(sys.argv)
    parser = argparse.ArgumentParser()
    parser.add_argument("infile", 
                            help="The video source to rip",
                            nargs='?',
                            default="dvd://1")
    parser.add_argument("--target",
                            help="Final target directory.",
                            default=None)
    parser.add_argument("--dvd-device",
                            help="Select the dvd device",
                            default='/dev/dvd')
    parser.add_argument("--ts",
                            help="Assume TS input file",
                            action='store_true',
                            default=False)
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
                            help="Langage code for audio tracks. Default 'fr,en'",
                            default='fr,en,unknown,xx,qaa,qad')
    parser.add_argument("--sub",
                            help="Langage code for subtitle tracks. Default to --lang",
                            default=None)
    parser.add_argument("--tune",
                            help="Tune for a specific media (default film)",
                            default="film")
    parser.add_argument("--interlaced",
                            help="Mark the video as being interlaced",
                            action='store_true',
                            default=None)
    parser.add_argument("--aspect",
                            help="Force aspect ratio",
                            default=None)
    parser.add_argument("--crop",
                            help="Crop picture",
                            default=None)
    parser.add_argument("--ss",
                            help="Start time",
                            default="00:00:00")
    parser.add_argument("--to",
                            help="End time",
                            default=None)
    parser.add_argument("--probesize",
                            help="Set the probesize in Mframes (x1000000)",
                            type=int,
                            default=None)
    parser.add_argument("--idxsize",
                            help="Set the idex (cues) size in bytes par hour",
                            type=int,
                            default=None)
    parser.add_argument("--vcodec",
                            help="Set the video codec (default libx264)",
                            default=None)
    parser.add_argument("--acodec",
                            help="Set the audio codec (default media depedent)",
                            default=None)
    parser.add_argument("--scodec",
                            help="Set the subtitle codec (default media depedent)",
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
    parser.add_argument("--nuke", 
                            help="Break the VOB file into individual streams then rebuild it. Fix some PTS issues",
                            action='store_true',
                            default=False)
    parser.add_argument("--ff", 
                            help="Raw argments passed to ffmpeg *unquoted*",
                            default='')
    parser.add_argument("--kid", 
                            help="Coma-separated list of stream ID to ignore",
                            default=None)

    args = parser.parse_args()

    print(args)

    dry_run = args.dry or False
    meta = Metadata(args.infile)
    meta._dvd = [p.strip() for p in args.dvd_device.split("+")]
    meta._out_format = args.container
    meta._lcodes = args.lang.split(',')
    meta._scodes = args.sub.split(',') if args.sub else meta._lcodes
    meta._tune = args.tune
    meta._force_dump = args.force_dump
    meta._force_conv = args.force_conv
    meta._target = args.target
    meta._ss = args.ss
    meta._to = args.to
    meta._ff = args.ff
    meta._kid = [int(i,base=0) for i in args.kid.split(',')] if args.kid else []

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
    if args.aspect is not None:
        meta.f_aspect_ratio = constantly(args.aspect)
    if args.crop is not None:
        meta.f_crop = constantly(args.crop)
    if args.idxsize is not None:
        meta.f_idxsize = constantly(args.idxsize)
    if args.probesize is not None:
        meta.f_probesize = constantly(args.probesize)

    if args.ts:
        meta.initFromTS()
    else:
        meta.initFromDVD()

    # override options
    if args.scodec is not None:
        meta._subformat = args.scodec
    if args.acodec is not None:
        meta._audioformat = args.acodec
    if args.vcodec is not None:
        meta._videoformat = args.vcodec

    actions = []
    if args.print_meta:
        actions.append(print_meta)
    if not args.ts:
        actions.append(dump)
    actions.append(idet)
    if not args.ts:
        actions.append(probe)
    if args.nuke:
        actions.append(nuke)
    actions.append(conv)
    if not args.ts:
        actions.append(chapters) 
        ### ^^^ XXX adding chapters to matroska files cause problems
        ### to some readers as they "push" the stream header data
        ### to the end of the file. In addition, mkvmerge
        ### seems to be unable to deal with ffmpeg encoded
        ### VOBSUB subtitles....
    actions.append(set_defaults)
    # actions.append(final_copy) ### <-- This was a "hack" to try to
                                 ### deal with "complex" matroska files
    actions.append(install)
    if (meta._dvd[-1].lower().endswith(".iso") or meta._dvd[-1].startswith('/dev/')):
        actions.append(clean_vob)

    infile = meta._fName

    for action in actions:
        infile = action(meta, infile)



