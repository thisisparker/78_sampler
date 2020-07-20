#!/usr/bin/env python3

import internetarchive as ia
import os
import random
import subprocess
import yaml

from operator import attrgetter

from mutagen.mp3 import MP3
from PIL import Image
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
    
    print("rolling video of",to_dl.name,sep=" ")

    command = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'panic']
    command.extend(['-i', to_dl.name, '-loop', '1', '-i', photo.name])
    command.extend(['-vf', 'scale=-1:480,pad=720:ih:(ow-iw)/2,fps=25'])
    if fade:
        command.extend(['-af','afade=t=out:st=138:d=2'])        
    command.extend(['-strict', '-2', '-ss', '0', '-to', str(timeout), 'merge.mp4'])

    subprocess.run(command)

    os.remove(to_dl.name)
    os.remove(photo.name)

    print(title.lower(), url, "merge.mp4", sep=" ")

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
