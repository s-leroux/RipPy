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
DDRESCUE="ddrescue -MA {device} {title}.iso {title}.log"
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

    info = ast.literal_eval(rawdata)

    title = info['title']
    run(DDRESCUE, device=device, title=title)
    run(EJECT, device=device)
    

