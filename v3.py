import asyncio
import edge_tts
import os
from pydub import AudioSegment
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip
import whisper



#------------------------- Ask the user to upload a file ---------------#
file_path = input("Enter the path to the .txt file: ")

TEXT = ""
try:
    with open(file_path, 'r', encoding="utf-8") as file:
        TEXT = file.read()
except FileNotFoundError:
    print(f"File not found: {file_path}")
    exit()

tempscript = TEXT.split("\n")
SCRIPT = [element for element in tempscript if element != '']

#----------------------- TTS Setup -----------------------#
VOICES = ['de-DE-AmalaNeural', 'de-DE-ConradNeural']
OUTPUT_PATH = "audios/"
os.makedirs(OUTPUT_PATH, exist_ok=True)

async def tts(text, output_filename, VOICE):
    communicate = edge_tts.Communicate(text, voice=VOICES[VOICE])
    await communicate.save(output_filename)

async def process_script(SCRIPT, OUTPUT_PATH):
    for i, line in enumerate(SCRIPT):
        audio_name = f"{i}.mp3"
        if line.startswith('Tom:'):
            line = line[len('Tom: '):]
            await tts(line, os.path.join(OUTPUT_PATH, audio_name), 1)
        elif line.startswith('Lisa:'):
            line = line[len('Lisa: '):]
            await tts(line, os.path.join(OUTPUT_PATH, audio_name), 0)
        
        print(f"Generated audio for line {i}: {line[:30]}...")
        await asyncio.sleep(1.5)  # small delay between requests

asyncio.run(process_script(SCRIPT, OUTPUT_PATH))

#----------------- Combine audio files -----------------#
audio_files = sorted([os.path.join(OUTPUT_PATH, f) for f in os.listdir(OUTPUT_PATH) if f.endswith(".mp3")],
                     key=lambda x: int(os.path.splitext(os.path.basename(x))[0]))

combined = AudioSegment.from_mp3(audio_files[0])
for file in audio_files[1:]:
    combined += AudioSegment.from_mp3(file)

combined_audio_path = "audios/full_audio.wav"
combined.export(combined_audio_path, format="wav")
print("✅ Audio combined:", combined_audio_path)

#----------------- Video background -----------------#
Background = input("Video file name (folder path: videos/) | default: mc.mp4: ")
if Background.strip() == "":
    Background = "mc"

video = VideoFileClip(f'videos/{Background}.mp4')
audio = AudioFileClip(combined_audio_path)
video = video.set_audio(audio).subclip(0, audio.duration)

#----------------- Whisper transcription -----------------#
print("Transcribing audio with Whisper...")
model = whisper.load_model("medium")
result = model.transcribe(combined_audio_path)

#----------------- Generate SRT and subtitle segments -----------------#
def format_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

subtitles = []
subtitle_segments = []

def split_text(text, max_words=5):
    words = text.split()
    return [" ".join(words[i:i+max_words]) for i in range(0, len(words), max_words)]

for i, segment in enumerate(result["segments"]):
    start = segment["start"]
    end = segment["end"]
    text = segment["text"].strip()
    
    chunks = split_text(text, max_words=5)
    duration_per_chunk = (end - start) / len(chunks) if len(chunks) > 0 else end - start
    
    for j, chunk in enumerate(chunks):
        chunk_start = start + j * duration_per_chunk
        chunk_end = chunk_start + duration_per_chunk
        subtitle_segments.append((chunk_start, chunk_end, chunk))
        
        start_str = format_time(chunk_start)
        end_str = format_time(chunk_end)
        subtitles.append(f"{len(subtitles)+1}\n{start_str} --> {end_str}\n{chunk}\n")

srt_path = "subtitles.srt"
with open(srt_path, "w", encoding="utf-8") as f:
    f.writelines(subtitles)
print("✅ Subtitles saved:", srt_path)

#----------------- Overlay subtitles on video -----------------#
def create_subtitle_clips(srt_file, video_width):
    clips = []
    for start_time, end_time, txt in subtitle_segments:
        clip = (
            TextClip(
                txt,
                fontsize=80,
                color='white',
                font='Arial-Bold',
                stroke_color='red',
                stroke_width=4,
                size=(video_width * 0.8, None),  # wrap text to 80% of video width
                method='caption'                # pygame
            )
            .set_position(('center', 'center'))
            .set_start(start_time)
            .set_end(end_time)
        )
        clips.append(clip)
    return clips

subtitle_clips = create_subtitle_clips(srt_path, video.w)
final_video = CompositeVideoClip([video, *subtitle_clips])
final_video.write_videofile("Full_video_with_subtitles.mp4", codec="libx264")
print("✅ Video with subtitles saved as Full_video_with_subtitles.mp4")
