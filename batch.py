import os
import fileinput
from shlex import quote as quote

for line in fileinput.input():
    volume, iso, title, episode, name = (item.strip() 
                                for item in line.split("|"))

    cmd = "python3 main.py --volume {volume} \
                           --episode {episode} \
                           --title {name} \
                           --dvd-device {iso} \
                           --target '/usr/local/share/xbmc/TV Shows' \
                           {title}"
    cmd = cmd.format(volume=quote(volume),
                     iso=quote(iso),
                     name=quote(name),
                     title=quote(title),
                     episode=quote(episode))

    os.system(cmd)

