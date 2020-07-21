#!/usr/bin/env python3

import internetarchive as ia
import os
import random
import shutil
import subprocess
import yaml

from operator import attrgetter

from mutagen.mp3 import MP3
from PIL import Image, ImageDraw, ImageOps
from twython import Twython

from georgeblood import blood

def main():
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    tune = random.choice(blood)
    item = ia.get_item(tune['identifier'])
    files = item.get_files(formats=['VBR MP3', 'Item Image'])

    l = list(files)

    mp3s = [f for f in l if f.format == 'VBR MP3']
    photos = [f for f in l if f.format == 'Item Image']

    photo = max(photos, key=attrgetter('size'))
    photo.download(photo.name)

    to_dl = min(mp3s, key=lambda s: len(s.name))

    title = item.metadata.get('title')
    artists = item.metadata.get('creator')
    artists = ', '.join(artists) if type(artists) is list else artists

    date = item.metadata.get('date')

    url = "https://archive.org/details/" + to_dl.identifier

    print("downloading", title)

    to_dl.download(to_dl.name)

    audio = MP3(to_dl.name)

    if audio.info.length < 140:
        timeout = audio.info.length
        fade = False
    else:
        timeout = 140
        fade = True

    if os.path.exists('temp'):
        shutil.rmtree('temp')

    os.makedirs('temp')

    size = (720,720)
    recimg = Image.open(photo.name)
    recimg = ImageOps.fit(recimg, size)

    mat = Image.new('L', size, color=255)
    draw = ImageDraw.Draw(mat)
    draw.ellipse((72,72) + (size[0]-72, size[1]-72), fill=0)

    print('rendering rotating record')

    for angle in range(0,360):
        rot = recimg.rotate(-angle)
        rot.paste((255,252,233), mask=mat)
        filename = 'img{:04d}.jpg'.format(abs(angle))
        rot.save(os.path.join('temp', filename))
    
    print("rolling video of",to_dl.name,sep=" ")

    command = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'panic']
    command.extend(['-i', to_dl.name, '-loop', '1', '-i', 'temp/img%04d.jpg'])
    if fade:
        command.extend(['-af','afade=t=out:st=138:d=2'])        
    command.extend(['-strict', '-2', '-ss', '0', '-to', str(timeout), 'merge.mp4'])

    subprocess.run(command)

    os.remove(to_dl.name)
    os.remove(photo.name)

    shutil.rmtree('temp')

    with open('config.yaml') as f:
        config = yaml.safe_load(f)

    twitter_app_key = config['twitter_app_key']
    twitter_app_secret = config['twitter_app_secret']
    twitter_oauth_token = config['twitter_oauth_token']
    twitter_oauth_token_secret = config['twitter_oauth_token_secret']

    twitter = Twython(twitter_app_key, twitter_app_secret, twitter_oauth_token, twitter_oauth_token_secret)

    with open('merge.mp4', 'rb') as f:
        response = twitter.upload_video(media=f, media_type='video/mp4', media_category='tweet_video', check_progress = True)

    status = " ".join([title.lower() + ' - ' + artists.lower(), url])
    print(status)
    twitter.update_status(status=status, media_ids=[response['media_id']])

if __name__ == '__main__':
    main()
