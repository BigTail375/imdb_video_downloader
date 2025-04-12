# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import os
import json
from urllib.request import urlopen

def download(video_url) :
    file_size_str = requests.head(video_url).headers['Content-Length']
    file_size = str(float(file_size_str)/1024/1024) 
    print(file_size + " MB")
    ru = urlopen(video_url)
    f = open("video.mp4", 'wb')
    
    file_size_dl = 0
    block_sz = 8192
    while True:
        buffer = ru.read(block_sz)
        if not buffer:
            break
        file_size_dl += len(buffer)
        s = file_size_dl/1024/1024
        if s % 5 == 0 :
            print(float(file_size_dl/1024/1024),"MB Downloaded")
        f.write(buffer)
    f.close()

def scrapeVidPage(video_id) :
    video_url = "https://www.imdb.com/video/" + video_id
    r = requests.get(url=video_url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(r.text, 'html.parser')
    script = soup.find("script",{'type': 'application/json'})
    json_object = json.loads(script.string)
    videos = json_object["props"]["pageProps"]["videoPlaybackData"]["video"]["playbackURLs"]

    for video in videos[1:]:
        video_link = video["url"]
        break
    return video_link



def start_video_download(video_id) :
    os.makedirs("videos", exist_ok=True)
    video_url = scrapeVidPage(video_id)
    download(video_url)

if __name__ == '__main__':
    # video_id="vi1143521817"
    # start_video_download(video_id)
    # print(scrapeVidTags('tt0944947'))
    pass