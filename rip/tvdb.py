#!/usr/bin/python3

import time
import argparse
import os
from os.path import join
import pathlib
import re
from bs4 import BeautifulSoup
from selenium import webdriver

SEARCH_AP = "https://thetvdb.com/search"
SERIES_RE = re.compile("/series/")

EPISODES_AP = "https://thetvdb.com/series/{id}/allseasons/official"
EPISODE_RE = re.compile("/series/[^/]+/episodes/[0-9]+")

import urllib.parse
def urlencode(endpoint, params):
    querystring = urllib.parse.urlencode(params)
    return endpoint + "?" + querystring

class Browser:
    def __init__(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--incognito')
        options.add_argument('--headless')

        self.driver = webdriver.Chrome("chromedriver", options=options)

    def get(self, endpoint, params = None):
        url = endpoint if not params else urlencode(endpoint, params)
        self.driver.get(url)
        return self.driver.page_source

class TVDB:
    def __init__(self):
        self.browser = Browser()

    def search(self, title):
        """ Query the TVDB search page to find results matching
            the given human-readable title.

            Return a (possibly empty) array of results.
        """
        retries = 3
        links = []

        while retries and not len(links):
            retries -= 1
            html = self.browser.get(SEARCH_AP,dict(query=title))

            # Process the HTML page
            soup = BeautifulSoup(html, "lxml")
            hits = soup.find(id="hits")
            links = hits.find_all("a", href=SERIES_RE)

        result = []
        for link in links:
            title = link.text
            if title != "":
                result.append(dict(
                    id=link["href"].replace("/series/",""),
                    title=link.text,
                ))

        return result

    def episodes(self, id):
        html = self.browser.get(EPISODES_AP.format(id=id))
        soup = BeautifulSoup(html, "lxml")
        links = soup.find_all("a", href=EPISODE_RE)
        episodes = {}
        for link in links:
            title = link.text.strip()
            parent = link.parent
            m = re.search("(\d+)x(\d+)", parent.text) or re.search("S(\d+)E(\d+)", parent.text)
            if m:
                season_num, episode_num = m.groups()
                season_num = int(season_num)
                episode_num = int(episode_num)
                
                season = episodes.setdefault(season_num, {})
                episode = season.setdefault(episode_num, {})
                episode["title"] = title

        return episodes

def load(title):
    tvdb = TVDB()
    matches = tvdb.search(title)
    try:
        id = matches[0]["id"];
    except IndexError:
        return {}

    return tvdb.episodes(id);

class DB:
    def __init__(self):
        self.aliases = {}
        self.db = {}

    def alias(self, key, value):
        self.aliases[key] = value

    def episodes(self, serie, season, episode):
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
