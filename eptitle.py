#!/usr/bin/python3

import requests
import time
import argparse
import os
from os.path import join
import pathlib
import re

FFILTER = re.compile("(.*)[.](\d+)x(\d+)[.](.*)[.][^.]+")
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
    def populate(src):
        for ep in src:
            m.setdefault(ep["season"], {})[ep["number"]] = dict(title=ep["name"], runtime=ep["runtime"])

    m = {}
    r = query(SINGLESEARCH_AP,dict(q=title, embed="alternatelists"))
    
    r = r.json() or {}
    embedded = r.setdefault("_embedded", {})
    alternatelists = embedded.setdefault("alternatelists", [])
    ep_href = r["_links"]["self"]["href"]

    r = query(ep_href + "/episodes")
    populate(r.json() or [])

    # Overwrite with data from alternatelists
    for lst in alternatelists:
        if lst["verbatim_order"]:
            r = query(lst["_links"]["self"]["href"]+"/alternateepisodes")
            populate(r.json() or [])
            break
    return m

class DB:
    def __init__(self):
        self.aliases = {}
        self.db = {}

    def alias(self, key, value):
        self.aliases[key] = value

    def title(self, serie, season, episode):
        serie = self.aliases.get(serie, serie)
        season=int(season)
        episode=int(episode)
        episodes = self.db.get(serie)
        if episodes is None:
            episodes = self.db[serie] = load(serie)

        ep = episodes.get(season, {}).get(episode)
        return ep and ep["title"]

def main():
    db = DB()

    parser = argparse.ArgumentParser()
    parser.add_argument("--alias", 
                            nargs='*',
                            default=[],
                            help="Serie alias")
    parser.add_argument("--fix", 
                            action="store_true",
                            help="Fix missing titles")
    parser.add_argument("--rename", 
                            action="store_true",
                            help="Replace existing titles")
    parser.add_argument("--force", 
                            action="store_true",
                            help="Replace existing files")
    parser.add_argument("path", 
                            help="The directory containing files to rename",
                            )
    args = parser.parse_args()
    path = args.path
    fix = args.fix
    force = args.force
    rename = args.rename
    for opt in args.alias:
        key, value = opt.split("=")
        db.alias(key, value)

    for root, dirs, files in os.walk(path):
        for fname in files:
            match = FFILTER.search(fname)
            if match:
                serie = match.group(1)
                season = int(match.group(2))
                episode = int(match.group(3))
                title = match.group(4)

                if not rename and title != serie:
                    continue

                title = db.title(serie, season, episode)
                if not title:
                    print("Not found:",serie,"episode ",season, episode)
                else:
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
                    
                    if force or not dst.exists():
                        print(src, "=>",dst.name)
                        if fix:
                            src.rename(dst)


if __name__ == "__main__":
    main()
