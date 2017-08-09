#!/usr/bin/env python3

import random
from georgeblood import blood
import internetarchive as ia
from operator import attrgetter
import os
import subprocess
from mutagen.mp3 import MP3
from twython import Twython
import yaml

def main():
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    tune = random.choice(blood)
    item = ia.get_files(tune['identifier'], formats=['VBR MP3', 'Item Image'])

    l = list(item)

    mp3s = [f for f in l if f.format == 'VBR MP3']
    photos = [f for f in l if f.format == 'Item Image']

    photo = max(photos, key=attrgetter('size'))
    photo.download(photo.name)

    to_dl = min(mp3s, key=attrgetter('name'))

    title = to_dl.name.split('.mp3')[0]
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
        config = yaml.load(f)

    twitter_app_key = config['twitter_app_key']
    twitter_app_secret = config['twitter_app_secret']
    twitter_oauth_token = config['twitter_oauth_token']
    twitter_oauth_token_secret = config['twitter_oauth_token_secret']

    twitter = Twython(twitter_app_key, twitter_app_secret, twitter_oauth_token, twitter_oauth_token_secret)

    with open('merge.mp4', 'rb') as f:
        response = twitter.upload_video(media=f, media_type='video/mp4', media_category='tweet_video', check_progress = True)

    status = " ".join([title.lower(), url])
    twitter.update_status(status=status, media_ids=[response['media_id']])

if __name__ == '__main__':
    main()
