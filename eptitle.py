import requests
import time
import argparse
import os
from os.path import join
import pathlib
import re

FFILTER = re.compile("(.*)[.](\d+)x(\d+)[.]\\1[.][^.]+")
SINGLESEARCH_AP = "http://api.tvmaze.com/singlesearch/shows"

def query(url, params={}, options={}):
    retries = options.get("retries", 6)
    sleep = options.get("sleep", 0.5)

    n = 0

    while True:
        n += 1
        r = requests.get(url, params)
        if n > retries:
            return r
        if (200 <= r.status_code < 500) and r.status_code != 429:
            return r

        time.sleep(sleep)
        sleep *= 2

def load(title):
    m = {}
    r = query(SINGLESEARCH_AP,dict(q=title, embed="episodes"))
    
    for ep in (r.json() or {}).get("_embedded",{}).get("episodes",[]):
        key = (ep["season"], ep["number"])
        title = ep["name"]

        m[key] = title

    return m

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--alias", 
                            nargs='*',
                            help="Serie alias")
    parser.add_argument("--dry", 
                            action="store_true",
                            help="Dry run")
    parser.add_argument("path", 
                            help="The directory containing files to rename",
                            )
    args = parser.parse_args()
    path = args.path
    dry = args.dry
    alias = {}
    for opt in args.alias:
        key, value = opt.split("=")
        alias[key] = value

    db = {}
    for root, dirs, files in os.walk(path):
        for fname in files:
            match = FFILTER.search(fname)
            if match:
                serie = match.group(1)
                season = int(match.group(2))
                episode = int(match.group(3))

                query = alias.get(serie, serie)
                episodes = db.get(query)
                if episodes is None:
                    episodes = db[serie] = load(serie)
                    if episodes == {}:
                        print("Not episode list found for",serie)
                        print("May I suggest using --alias?")

                title = episodes.get((season, episode))
                if title:
                    src = pathlib.Path(root,fname)
                    nname = "{serie}.{season}x{episode:02}.{title}{suffix}".format(
                            serie=serie,
                            season=season,
                            episode=episode,
                            title=title,
                            suffix=src.suffix)
                    nname = nname.replace("/","-")
                    nname = nname.replace("\\","-")
                    dst = pathlib.Path(root, nname)
                    
                    if not dst.exists():
                        print(src, "=>",dst.name)
                        if not dry:
                            src.rename(dst)


if __name__ == "__main__":
    main()
