import os
import re
import fileinput
from shlex import quote as quote
import eptitle

db = eptitle.DB()
extra=""

for line in fileinput.input():
    line = line.strip()

    if not line or line[0]=="#":
        continue

    if line[0]=='@':
        # Set options
        extra=line[1:]
        continue

    volume, iso, title, episode_or_year, name = (item.strip() 
                                for item in line.split("|"))
    name = name.split('#',1)[0]
    name = name.strip()


    if re.match("\d{4}",episode_or_year):
        if not name:
            name = volume
        cmd = "python3 main.py --volume {volume} \
                               --title {name} \
                               --year {episode_or_year} \
                               --dvd-device {iso} \
                               --target '/usr/local/share/xbmc/Movies' \
                               {extra} \
                               {title}"
        
    else:
        if not name:
            try:
                season, ep, *tail = episode_or_year.split("x")
                name = db.title(volume, season, ep) or volume
            except:
                name = volume

        cmd = "python3 main.py --volume {volume} \
                               --episode {episode_or_year} \
                               --title {name} \
                               --dvd-device {iso} \
                               --target '/usr/local/share/xbmc/TV Shows' \
                               {extra} \
                               {title}"

    cmd = cmd.format(volume=quote(volume),
                     iso=quote(iso),
                     name=quote(name),
                     title=quote(title),
                     episode_or_year=quote(episode_or_year),
                     extra=extra)
    os.system(cmd)

