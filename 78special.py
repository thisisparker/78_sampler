#!/usr/bin/env python3

import internetarchive as ia
import cv2
import os
import numpy as np
import random
import shutil
import subprocess
import sys
import yaml

from operator import attrgetter

from colorthief import ColorThief
from mutagen.mp3 import MP3
from PIL import Image, ImageDraw, ImageOps
from twython import Twython

from georgeblood import blood

def get_label_circle(fullsize_path):
    fullsize = Image.open(fullsize_path)
    fullsize_dimensions = fullsize.size

    ratio = fullsize_dimensions[0]/640

    crop = ImageOps.fit(fullsize, (640,640))
    filename = '640_' + fullsize_path
    crop.save(filename)

    src = cv2.imread(filename)
    blur = cv2.medianBlur(src, 5)
    gray = cv2.cvtColor(blur, cv2.COLOR_RGBA2GRAY)

    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 100,
                               param1=150, param2=50, minRadius=150, maxRadius=225)

    os.remove(filename)

    if circles is not None:
        circles = np.round(circles[0,:]).astype('int')
        x, y, r = [int(val * ratio) for val in circles.tolist()[0]]

        return x, y, r

    else:
        return None

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

    center_x, center_y, radius = get_label_circle(photo.name)

    radius += 20

    raw_img = Image.open(photo.name)
    label_crop = raw_img.crop((center_x - radius, center_y - radius,
                                 center_x + radius, center_y + radius))

    label_crop.save('label.jpg')
    colorthief = ColorThief('label.jpg')
    dominant = colorthief.get_color(quality=1)
    os.remove('label.jpg')

    label_crop = ImageOps.fit(label_crop, (400,400))
    label_mask = Image.new('L', (400,400), color=0)
    draw = ImageDraw.Draw(label_mask)
    draw.ellipse((0,0,400,400), fill=255)

    size = (720,720)

    recimg = Image.new('RGB', size, 0)
    recimg.paste(label_crop, box=(160,160), mask=label_mask)

    mat = Image.new('L', size, color=255)
    draw = ImageDraw.Draw(mat)
    draw.ellipse((36,36) + (size[0]-36, size[1]-36), fill=0)

    print('rendering rotating record')

    for index, angle in enumerate(range(0,360,3)):
        rot = recimg.rotate(-angle)
        rot.paste(dominant, mask=mat)
        filename = 'img{:04d}.jpg'.format(index)
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
