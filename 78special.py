#!/usr/bin/env python3

import argparse
import os
import random
import shutil
import subprocess
import sys

import internetarchive as ia
import cv2
import numpy as np
import yaml

from colorthief import ColorThief
from mutagen.mp3 import MP3
from PIL import Image, ImageDraw, ImageOps
from twython import Twython

from georgeblood import blood

def get_items_list():
    return [item['identifier'] for item in blood]

def get_item(items):
    return random.choice(items)

def get_image(files):
    images = [f for f in files if f.format == 'Item Image']
    photo = max(images, key=lambda i: i.size)
    return photo

def get_audio(files):
    mp3s = [f for f in files if f.format == 'VBR MP3']
    track = min(mp3s, key=lambda s: len(s.name))
    return track

def get_label_circle(fullsize_path):
    fullsize = Image.open(fullsize_path)
    fullsize_dimensions = fullsize.size

    ratio = fullsize_dimensions[0]/640

    crop = ImageOps.fit(fullsize, (640,640))
    filename = ''.join(['640_' + fullsize_path])
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

def crop_label(imagepath, x, y, r):
    r += 20

    fullsize = Image.open(imagepath)
    label_crop = fullsize.crop((x - r, y - r, x + r, y + r))

    return label_crop

def get_color(image, cleanup=True):
    image.save('label.jpg')
    colorthief = ColorThief('label.jpg')
    if cleanup:
        os.remove('label.jpg')
    palette = colorthief.get_palette(color_count=2, quality=1)
    for color in palette:
        if all(channel < 64 for channel in color):
            dominant = (255, 252, 233)
            continue
        else:
            dominant = color
            break
    if dominant is None:
        return (255, 252, 233)
    else:
        return dominant

def render_record_frames(label_crop, bg_color, size=(720,720), angles_per_frame=3,
                         directory="temp"):
    label_crop = ImageOps.fit(label_crop, (400,400))
    label_mask = Image.new('L', (400,400))
    draw = ImageDraw.Draw(label_mask)
    draw.ellipse((0,0,400,400), fill=255)

    recimg = Image.new('RGB', size, 0)
    recimg.paste(label_crop, box=(160,160), mask=label_mask)

    mat = Image.new('L', size, color=255)
    draw = ImageDraw.Draw(mat)
    draw.ellipse((36,36,684,684), fill=0)

    for index, angle in enumerate(range(0, 360, angles_per_frame)):
        rot = recimg.rotate(-angle)
        rot.paste(bg_color, mask=mat)
        filename = 'img{:04d}.jpg'.format(index)
        rot.save(os.path.join(directory, filename))

def render_video(image_directory, audio_file, max_time=140, output_file='merge.mp4'):
    audio = MP3(audio_file)

    if audio.info.length < max_time:
        timeout = audio.info.length
        fade = False
    else:
        timeout = max_time
        fade = True

    command = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'panic']
    command.extend(['-i', audio_file, '-loop', '1',
                    '-i', '{}/img%04d.jpg'.format(image_directory)])
    if fade:
        command.extend(['-af','afade=t=out:st=138:d=2'])        
    command.extend(['-strict', '-2', '-ss', '0', '-to', str(timeout), output_file])

    subprocess.run(command)

def post_tweet(status, video_file):
    with open('config.yaml') as f:
        config = yaml.safe_load(f)

    twitter_app_key = config['twitter_app_key']
    twitter_app_secret = config['twitter_app_secret']
    twitter_oauth_token = config['twitter_oauth_token']
    twitter_oauth_token_secret = config['twitter_oauth_token_secret']

    twitter = Twython(twitter_app_key, twitter_app_secret, twitter_oauth_token, twitter_oauth_token_secret)

    with open(video_file, 'rb') as f:
        response = twitter.upload_video(media=f, media_type='video/mp4',
                                        media_category='tweet_video', check_progress = True)

    twitter.update_status(status=status, media_ids=[response['media_id']])


def run(ia_id=None, cleanup=True, to_tweet=True, quiet=False):
    if ia_id is None:
        items = get_items_list()
        ia_id = get_item(items)

    item = ia.get_item(ia_id)

    files = list(item.get_files(formats=['VBR MP3', 'Item Image']))
    photo = get_image(files)
    track = get_audio(files)

    title = item.metadata.get('title')
    date = item.metadata.get('date', '')

    date = ''.join(['(', date.split('-')[0], ')']) if date else ''
    title = ' '.join([title, date]) if date else title

    artists = item.metadata.get('creator')
    artists = artists[0] if type(artists) is list else artists

    url = "https://archive.org/details/" + item.identifier

    if not quiet:
        print("downloading", title)

    track.download(track.name)
    photo.download(photo.name)

    if os.path.exists('temp'):
        shutil.rmtree('temp')

    os.makedirs('temp')

    if not quiet:
        print("finding label")
    try:
        center_x, center_y, radius = get_label_circle(photo.name)
    except:
        sys.exit('Unable to find label in item image.')

    label_crop = crop_label(photo.name, center_x, center_y, radius)
    bg_color = get_color(label_crop, cleanup)

    if not quiet:
        print("rendering spinning record frames")
    render_record_frames(label_crop, bg_color)

    if not quiet:
        print("rendering video")
    render_video('temp', track.name)

    if cleanup:
        os.remove(track.name)
        os.remove(photo.name)

        shutil.rmtree('temp')

    status = " ".join([title.lower() + ' - ' + artists.lower(), url])

    if to_tweet:
        post_tweet(status, video_file='merge.mp4')
        if not quiet:
            print('tweet posted!')
    else:
        print(status)

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('-k', '--keep', action='store_true',
                        help="""keep intermediate files after completion""")
    parser.add_argument('-i', '--id', action='store', default=None,
                        help="""explicitly provide an
                        Internet Archive identifier for download""")
    parser.add_argument('-d', '--dryrun', action='store_true',
                        help="""download files and render video but
                        do not tweet""")
    parser.add_argument('-q', '--quiet', action='store_true',
                        help="""suppress progress output""")

    args = parser.parse_args()
    cleanup = not args.keep
    ia_id = args.id
    to_tweet = not args.dryrun
    quiet = args.quiet

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    run(ia_id, cleanup, to_tweet, quiet)

if __name__ == '__main__':
    main()
