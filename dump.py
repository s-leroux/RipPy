#!/usr/bin/python3

import argparse
import ast

from subprocess import Popen,call,PIPE,STDOUT, CalledProcessError
import shutil
from pipes import quote
from io import StringIO, TextIOWrapper
import sys
import os

LSDVD="lsdvd -Oy {device}"
DDRESCUE="ddrescue -MA {device} --no-scrap --timeout={timeout} --unidirectional --sector-size=2048 --skip-size=64KiB {title}.ISO {title}.LOG"
EJECT="eject {device}"
            
def _pipe(cmd, stdout=PIPE, stderr=sys.stderr, args={}):
    cmd = cmd.format(**{k:quote(v) for k,v in args.items()})

    print("Running", cmd)
    return Popen(cmd,
                 stdout = stdout,
                 stderr = stderr,
                 shell=True) ### !!! This assume proper argument escaping

def wait(proc):
    returncode = proc.wait()
    if returncode:
        raise CalledProcessError(returncode, proc.args)

    return returncode
            
def pipe(cmd, **kwargs):
    return _pipe(cmd, stdout=PIPE, stderr=sys.stderr, args=kwargs)
            
def run(cmd, **kwargs):
    proc = _pipe(cmd, stdout=sys.stdout, stderr=sys.stderr, args=kwargs)
    return wait(proc)

def collect_and_display(proc):
    result = []
    stream = TextIOWrapper(proc.stdout,errors='ignore')
    for line in stream:
        print(line, end="")
        result.append(line)

    return "".join(result)

def collect(proc):
    stream = TextIOWrapper(proc.stdout,errors='ignore')
    output = stream.read()
    wait(proc)

    return output

def display(proc):
    stream = TextIOWrapper(proc.stdout,errors='ignore')
    for line in stream:
        print(line, end="")

    returncode = proc.wait()
    if returncode:
        raise CalledProcessError(returncode, proc.args)

def run_and_display(cmd, **kwargs):
    display(pipe(cmd, **kwargs))

def make_lst_file(lsdvd):
    fmt = "{name:25s} | {fname:>16s} | dvd://{ix:<3d} | 2000 | # {h:3d}:{m:02d}:{s:04.1f}"
    threshold = 60*4 # four minutes

    stem = lsdvd['file']
    if lsdvd['device']:
        fname = lsdvd['device']
    else:
        fname = lsdvd['file'] + '.ISO'

    title = lsdvd['title']
    name = title.replace("_"," ").title()

    lstname = "{fname}.LST".format(fname=stem)
    print("WRITING", lstname)
    with open(lstname, "at") as f:
        if f.tell() > 0:
            # File was already exisiting and not empty
            # Abort
            print(lstname, "already existing")
            return

        print("@--tune film", file=f)
        for ix, length in [(int(track['ix']), float(track['length']))
                                for track in lsdvd['track']]:
            if length > threshold:
                m, s = divmod(length, 60)
                h, m = divmod(m, 60)
                print(fmt.format(fname=fname, name=name, ix=ix, h=int(h), m=int(m), s=s),file=f)
            

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodump", 
                            help="Don't run ddrescue",
                            action='store_true',
                            default=False)
    parser.add_argument("--title", 
                            help="Force title",
                            default="")
    parser.add_argument("--tag", 
                            help="Extra tag used when naming output file",
                            default="")
    parser.add_argument("--timeout", 
                            help="Read timeout for ddrescue",
                            default="3000s")
    parser.add_argument("device", 
                            help="The block device containing the media",
                            nargs='?',
                            default="/dev/sr0")
    args = parser.parse_args()
    device = args.device
    timeout = args.timeout
    nodump = args.nodump

    proc = pipe(LSDVD, device=device)
    rawdata = collect(proc)

    if rawdata.startswith("lsdvd = "):
        #                  01234567
        rawdata = rawdata[8:]

    lsdvd = ast.literal_eval(rawdata)

    if args.title:
        lsdvd['title'] = args.title

    title = lsdvd['title']
    if nodump:
        lsdvd['device'] = device
    else:
        lsdvd['device'] = None

    if args.tag:
        lsdvd['file'] = "-".join((title, args.tag))
    else:
        lsdvd['file'] = title

    make_lst_file(lsdvd)
    if not nodump:
        run(DDRESCUE, device=device, title=lsdvd['file'], timeout=timeout)
        run(EJECT, device=device)
    

if __name__ == "__main__":
    try:
        main()
    except CalledProcessError as err:
        print("Error:",str(err), file=sys.stderr)
