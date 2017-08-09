#!/usr/bin/env python3

import random
from georgeblood import blood
import internetarchive
from operator import attrgetter
import os

def main():
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    tune = random.choice(blood)
    item = internetarchive.get_files(tune['identifier'], formats=['VBR MP3', 'Item Image'])

    l = list(item)

    mp3s = [f for f in l if f.format == 'VBR MP3']
    photos = [f for f in l if f.format == 'Item Image']

    photo = max(photos, key=attrgetter('size'))
    photo.download(photo.name)

    to_dl = min(mp3s, key=attrgetter('name'))
    to_dl.download(to_dl.name)

    print(to_dl.name)

if __name__ == '__main__':
    main()
