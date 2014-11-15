import os
import re
import fileinput
from shlex import quote as quote

for line in fileinput.input():
    line = line.strip()
    if not line or line[0] == '#':
        continue

    if line[0]=='@':
        # Set options
        os.environ['RIP_OPT']=line[1:]
        continue

    volume, iso, title, episode_or_year, name = (item.strip() 
                                for item in line.split("|"))

    if re.match("\d{4}",episode_or_year):
        cmd = "python3 main.py --volume {volume} \
                               --title {name} \
                               --year {episode_or_year} \
                               --dvd-device {iso} \
                               --target '/usr/local/share/xbmc/Movies' \
                               $RIP_OPT \
                               {title}"
        
    else:
        cmd = "python3 main.py --volume {volume} \
                               --episode {episode_or_year} \
                               --title {name} \
                               --dvd-device {iso} \
                               --target '/usr/local/share/xbmc/TV Shows' \
                               $RIP_OPT \
                               {title}"

    cmd = cmd.format(volume=quote(volume),
                     iso=quote(iso),
                     name=quote(name),
                     title=quote(title),
                     episode_or_year=quote(episode_or_year))
    os.system(cmd)

