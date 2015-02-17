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
DDRESCUE="ddrescue -MA {device} {title}.ISO {title}.LOG"
EJECT="eject {device}"
            
def _pipe(cmd, stdout=PIPE, stderr=STDOUT, args={}):
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
    return _pipe(cmd, stdout=PIPE, stderr=STDOUT, args=kwargs)
            
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
    return stream.read()

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
    fmt = "{name:25s} | {title:>12s}.ISO | dvd://{ix:<3d} | 2000 | # {h:3d}:{m:02d}:{s:04.1f}"
    threshold = 60*4 # four minutes

    title = lsdvd['title']
    name = title.replace("_"," ").title()

    fname = "{title}.LST".format(title=title)

    with open(fname, "at") as f:
        if f.tell() > 0:
            # File was already exisiting and not empty
            # Abort
            print(fname, "already existing")
            return

        for ix, length in [(int(track['ix']), float(track['length']))
                                for track in lsdvd['track']]:
            if length > threshold:
                m, s = divmod(length, 60)
                h, m = divmod(m, 60)
                print(fmt.format(title=title, name=name, ix=ix, h=int(h), m=int(m), s=s),file=f)
            

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("device", 
                            help="The block device containing the media",
                            nargs='?',
                            default="/dev/sr0")
    args = parser.parse_args()
    device = args.device

    proc = pipe(LSDVD, device=device)
    rawdata = collect(proc)

    if rawdata.startswith("lsdvd = "):
        #                  01234567
        rawdata = rawdata[8:]

    lsdvd = ast.literal_eval(rawdata)

    title = lsdvd['title']
    make_lst_file(lsdvd)
    run(DDRESCUE, device=device, title=title)
    run(EJECT, device=device)
    

