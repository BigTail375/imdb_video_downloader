from bs4 import BeautifulSoup
import requests, json, os, pickle
from moviepy.video.fx.resize import resize as mp_resize
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import moviepy.editor as mp
import ffmpeg
from PIL import Image
import assemblyai as aai
from deep_translator import GoogleTranslator
import pysrt
from pymongo import MongoClient, DESCENDING
import uuid
from datetime import datetime
import shutil

from download_video_by_video_Id import start_video_download

# MongoDB connection
client = MongoClient("mongodb://localhost:27017")
db = client["image_database"]
collection_image = db["images"]
collection_audio = db["audio"]

def custom_resize(clip, newsize):
    return mp_resize(clip, newsize, Image.LANCZOS)

def mili_to_string(milis):
    ms = milis % 1000
    sec = milis // 1000 % 60
    min = milis // 1000 // 60 % 60
    hour = milis // 1000 // 3600
    return f'{hour:02d}:{min:02d}:{sec:02d},{ms:03d}'

def get_video_id_list(imdb_id):
    url = "https://www.imdb.com/title/" + str(imdb_id) + "/videogallery?sort=date&sortDir=asc"
    r = requests.get(headers={'User-Agent': 'Mozilla/5.0'},url=url)
    soup = BeautifulSoup(r.text, 'html.parser')

    video_id_list = []
    for a_tag in soup.find_all('a', class_="ipc-lockup-overlay ipc-focusable"):
        href = a_tag.get('href')
        if href:
            # Construct the full URL if needed
            full_url = href.split('/')[2]
            if full_url.startswith('vi'):
                video_id_list.append(full_url)
    return video_id_list

def scrape_video_tags(imdb_id):
    video_url = "https://www.imdb.com/title/" + imdb_id
    r = requests.get(url=video_url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Find elements with specific class and get their text
    chips = soup.find_all("a", class_="ipc-chip ipc-chip--on-baseAlt")
    chip_texts = [chip.get_text(strip=True) for chip in chips]
    
    return chip_texts

def process_video(input_video_path, tag_list):
    # Load the video
    clip = VideoFileClip(input_video_path)
    
    # Check the aspect ratio and apply appropriate resizing
    if clip.w > clip.h:
        # Wider than tall, resize to max width of 640 and height of 360
        target_width, target_height = 640, 360
    else:
        # Taller than wide, resize to max width of 360 and height of 460
        target_width, target_height = 360, 460
    
    # Calculate new dimensions to maintain aspect ratio
    aspect_ratio = clip.w / clip.h
    if clip.w > target_width or clip.h > target_height:
        if clip.w > clip.h:  # Wider than tall
            new_width = target_width
            new_height = int(target_width / aspect_ratio)
        else:  # Taller than wide or square
            new_height = target_height
            new_width = int(target_height * aspect_ratio)
        clip = custom_resize(clip, (new_width, new_height))

    video_duration = clip.duration
    segment_duration = 5
    num_segments = int(video_duration // segment_duration)
    
    for i in range(num_segments):
        try:
            # Calculate the video count
            video_count = len(os.listdir(OUTPUT_DIR))
            start_time = i * segment_duration
            end_time = start_time + segment_duration
            segment = clip.subclip(start_time, end_time)

            # segment_mp4_path = os.path.join(OUTPUT_DIR, f"segment_{i + 1}.mp4")
            # segment.write_videofile(segment_mp4_path, codec="libx264", audio_codec="aac")
            audio_filename = f'{uuid.uuid4()}.mp3'
            segment_audio_path = os.path.join(OUTPUT_DIR, audio_filename)
            segment.audio.write_audiofile(segment_audio_path)

            collection_audio.insert_one({
                "folder_path": audio_filename,
                "upload_time": datetime.now().timestamp()
            })

            # Set GIF frame rate to 1/4 of the video frame rate

            gif_frame_rate = clip.fps / 4
            filename = f'{uuid.uuid4()}.gif'
            segment_gif_path = os.path.join(OUTPUT_DIR, filename)
            segment.write_gif(segment_gif_path, fps=gif_frame_rate)
            collection_image.insert_one({
                "folder_path": filename,
                "audio_path": audio_filename,
                "tags": tag_list,
                "vote_count": 0,
                "upload_time": datetime.now().timestamp()
            })

            times = [start_time + (segment_duration / 5) * j for j in range(1, 5)]
            images_2x2 = [segment.get_frame(t) for t in times]
            
            images_2x2_grid = Image.new("RGB", (images_2x2[0].shape[1] * 2, images_2x2[0].shape[0] * 2))
            images_2x2_grid.paste(Image.fromarray(images_2x2[0]), (0, 0))
            images_2x2_grid.paste(Image.fromarray(images_2x2[1]), (images_2x2[1].shape[1], 0))
            images_2x2_grid.paste(Image.fromarray(images_2x2[2]), (0, images_2x2[2].shape[0]))
            images_2x2_grid.paste(Image.fromarray(images_2x2[3]), (images_2x2[3].shape[1], images_2x2[3].shape[0]))

            filename = f'{uuid.uuid4()}.png'
            images_2x2_grid.save(os.path.join(OUTPUT_DIR, filename))
            collection_image.insert_one({
                "folder_path": filename,
                "audio_path": "",
                "tags": tag_list,
                "vote_count": 0,
                "upload_time": datetime.now().timestamp()
            })

            times = [start_time + (segment_duration / 4) * j for j in range(1, 4)]
            images_1x3 = [segment.get_frame(t) for t in times]

            images_1x3_grid = Image.new("RGB", (images_1x3[0].shape[1] * 3, images_1x3[0].shape[0]))
            for idx, img in enumerate(images_1x3):
                images_1x3_grid.paste(Image.fromarray(img), (images_1x3[idx].shape[1] * idx, 0))
                
            filename = f'{uuid.uuid4()}.png'
            images_1x3_grid.save(os.path.join(OUTPUT_DIR, filename))
            collection_image.insert_one({
                "folder_path": filename,
                "audio_path": "",
                "tags": tag_list,
                "vote_count": 0,
                "upload_time": datetime.now().timestamp()
            })

            images_3x1_grid = Image.new("RGB", (images_1x3[0].shape[1], images_1x3[0].shape[0] * 3))
            for idx, img in enumerate(images_1x3):
                images_3x1_grid.paste(Image.fromarray(img), (0, images_1x3[idx].shape[0] * idx))
            
            filename = f'{uuid.uuid4()}.png'
            images_3x1_grid.save(os.path.join(OUTPUT_DIR, filename))
            collection_image.insert_one({
                "folder_path": filename,
                "audio_path": "",
                "tags": tag_list,
                "vote_count": 0,
                "upload_time": datetime.now().timestamp()
            })

        except:
            continue
    clip.close()

def extract_audio(mp4_file_path, mp3_file_path):
    # Load the video file
    video = VideoFileClip(mp4_file_path)
    
    # Extract audio and write it to an mp3 file
    audio = video.audio
    audio.write_audiofile(mp3_file_path)

    # Close resources
    audio.close()
    video.close()

def extract_subtitle(mp3_file_path):
    aai.settings.api_key = "731cf44df19443f0a2c3ba7c5cdc5995" 
    audio_file = ("audio.mp3")
    config = aai.TranscriptionConfig(speaker_labels=True)
    transcript = aai.Transcriber().transcribe(audio_file, config)
    # with open('utterances.json', 'wb') as f:
    #     pickle.dump(transcript.utterances, f)
    return transcript.utterances

def convert_subtitle(utterances):
    # with open('utterances.json', 'rb') as f:
    #     utterances = pickle.load(f)
    
    with open('subtitle.srt', 'w') as f:
        srt_index = 1
        for utterance in utterances:
            print(utterance.text)
            start_index = 0
            words = utterance.words
            for (word_index, word) in enumerate(words):
                if word.text.endswith('.') or word.text.endswith('?'):
                    srt_text = " ".join([word.text for word in words[start_index:word_index + 1]])
                    start_time = words[start_index].start
                    end_time = words[word_index].end

                    f.write(f'{srt_index}\n')
                    f.write(f'{mili_to_string(start_time)} --> {mili_to_string(end_time)}\n')
                    f.write(f'{srt_text[:-1]}\n\n')

                    srt_index += 1
                    start_index = word_index + 1

def combine_subtitle(video_path, subtitle_path, output_path):
    # Load the video file
    video = mp.VideoFileClip(video_path)

    # Save a temporary copy of the video without audio, if necessary
    temp_video_path = "temp_video.mp4"
    video.write_videofile(temp_video_path, codec="libx264")

    # Use ffmpeg to add subtitles to the video
    ffmpeg.input(temp_video_path).output(
        output_path, vf=f"subtitles={subtitle_path}"
    ).run(overwrite_output=True)

def batch_translate(text, source_lang, target_lang):
    # Translate the concatenated text at once
    return GoogleTranslator(source=source_lang, target=target_lang).translate(text)

def translate_subtitle(file_path, target_languages):
    subs = pysrt.open(file_path)

    # Combine all subtitle texts into one long string with new lines
    all_text = "\n".join([sub.text for sub in subs])

    for lang in target_languages:
        # Translate the entire batch
        try:
            translated_text = batch_translate(all_text, 'en', lang)
            translated_lines = translated_text.split('\n')
            
            # Assign translated lines back to subtitle items
            for i, sub in enumerate(subs):
                sub.text = translated_lines[i] if i < len(translated_lines) else sub.text

            # Save the translated subtitles to a new file
            output_file = f"subtitle/{file_path.split('.srt')[0]}_{lang}.srt"
            subs.save(output_file, encoding='utf-8')
            print(f"Translated subtitles saved to: {output_file}")
        
        except Exception as e:
            print(f"Error translating subtitles to {lang}: {e}")

JSON_PATH = 'json/'
OUTPUT_DIR = '/data/img'
# OUTPUT_DIR = R'C:\xampp\htdocs\img'
VIDEO_DIR = '/data/video'

top_languages = {
    "en": "English",
    "zh-CN": "Chinese",
    "es": "Spanish",
    "hi": "Hindi",
    "ar": "Arabic",
    "bn": "Bengali",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "de": "German",
    "fr": "French",
    "ur": "Urdu",
    "it": "Italian",
    "tr": "Turkish",
    "ko": "Korean",
    "vi": "Vietnamese",
    "fa": "Persian",
    "pl": "Polish",
    "uk": "Ukrainian",
    "nl": "Dutch",
    "th": "Thai",
    "ms": "Malay",
    "sw": "Swahili",
    "ta": "Tamil",
    "mr": "Marathi",
    "te": "Telugu",
    "id": "Indonesian",
    "ro": "Romanian",
    "hu": "Hungarian",
    "el": "Greek"
}

if __name__ == '__main__':
    # tag_list = ['happy', 'sad', 'safe']
    # process_video('subtitle.mp4', tag_list)
    # pass

    json_index = 0
    try:
        with open('index.txt', 'r') as f:
            json_index = int(f.read())
    except:
        json_index = 0
    json_paths = os.listdir(JSON_PATH)

    for i in range(json_index, len(json_paths)):
        json_file = json_paths[i]
        json_path = os.path.join(JSON_PATH, json_file)
        print(f'json file : {json_path}')
        with open(json_path, 'r') as f:
            data = json.load(f)

        for movie in data:
            imdb_id = movie['ImdbId']
            print (f'imdb_d:{imdb_id}')
            tag_list = scrape_video_tags(imdb_id)
            video_id_list = get_video_id_list(imdb_id)
            print (f'video list {str(video_id_list)}')
            if video_id_list:
                for video_id in video_id_list:
                    try:
                        start_video_download(video_id)
                        shutil.move('video.mp4', os.path.join(VIDEO_DIR, f'{uuid.uuid4()}.mp4'))
                    except:
                        continue