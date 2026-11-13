# Clip Studio

Make a short video on your Windows PC. It is free. It stays on your computer. You do not need Grok Bot.

You will see a black window and a page in your browser. Leave the black window open while you work. Close it when you are done.

## 1. Put the folder on your PC

Download this whole project. Unzip it if it is a zip file.

Do not run the files from inside the zip. Open the unzipped folder, then open the `studio` folder.

Keep the whole project. Do not pull the `studio` folder out by itself. The letters on the video come from a folder next to it.

## 2. Install one time

1. Double-click `install.bat`.
2. If Windows asks, choose More info, then Run anyway.
3. Leave the window open. The first time is slow. It downloads Python, the video tool, and the voice.
4. Wait until it says **Done**.
5. You do not need an admin password. If a box asks for one, press No and read the words in the black window.

Joe's voice is a big extra download. If that part fails, the rest still works. You can use the fast voice.

## 3. Open the app

1. Double-click `start.bat`.
2. Your browser opens to Clip Studio.
3. Leave the black window open. If you close it, the page stops.

If the browser does not open, look at the black window for a line like `http://127.0.0.1:7860/` and type that into the browser.

## 4. Make a video

1. Paste a YouTube link, or a public X link. Press **Get the video**. Or choose a file from your computer.
2. Wait. The first time, the app downloads the tool that reads the words. A short clip takes a few minutes. A long video takes longer. Leave the window open.
3. Read the words. Click a suggested moment, or type a start time and an end time. You can type `1:30` or `90`.
4. Fill in the titles. They show in capital letters. Side notes are optional. Put one note on each line.
5. Leave the sound on **No music (voice only)** unless you want quiet music.
6. Press **Make the video**.
7. Press **Save the video**. The file is also in the `studio\work` folder.

The picture is 1920 by 1080, on a pure black background. Check **Also make a tall phone video** if you want 1080 by 1920 too.

## 5. Optional voice

In step 4, type a few sentences and press **Make the voice**.

- Fast male voice and fast female voice work as soon as install is done. The first time, the app downloads the voice. That takes a few minutes.
- Grandfather Joe sounds like the reference clip in the app folder. He needs the extra install. If he is not there, the fast voice still works.

To put that voice on the video, check **Use the voice I made** in step 3, then press **Make the video**.

## 6. Prompts

Step 5 in the app has Copy buttons. Paste the prompt into free Grok or ChatGPT.

The same words are in `PROMPTS.md` if you want to read them on their own.

## If something goes wrong

**The page will not load.**
The black window has to stay open. Double-click `start.bat` again.

**A YouTube or X link failed.**
Press **Update the downloader** in the app, or double-click `update_ytdlp.bat`. Then close the black window and double-click `start.bat`.

If YouTube says the downloader must sign in, that is YouTube's check, not a broken app. Try the link again later, or choose a file from your computer.

X posts have to be public. A private post, or a post that asks you to log in, will not download. Copy the link from a public post.

**The first run is very slow.**
That is normal. The app is downloading the word reader and the fast voice. Later videos are faster. There is no graphics card step. This app is built for a normal PC.

**Joe's voice failed.**
Use the fast voice. You can double-click `install.bat` again. If Joe fails a second time, ignore that part. The app still makes videos.

**It says the video tool is missing.**
Double-click `install.bat` again and wait for Done. If it still fails, download ffmpeg for Windows, unzip it, and put `ffmpeg.exe` and `ffprobe.exe` in:

`studio\tools\ffmpeg\bin\`

**Windows said it protected your PC.**
Click More info, then Run anyway. These are script files for this app, not a store installer.

**The video is too long to wait for.**
Cut a shorter part. About 90 to 120 seconds is the sweet spot. The whole file is read first, so a one hour video takes a long time before you can cut it.

## What the video follows

- Black background. Not navy.
- A frame around the footage, with the source name.
- Words that light up as they are spoken.
- A hook at the start and a short end card.
- Simple moving notes on the side.
- No whoosh sounds.
- No music, unless you turn music on. Music is a quiet tune made on your computer.
- Sound leveled to about -14 LUFS, peak at or under -1 dB.
- MP4, H.264 video, AAC sound, under 15 MB.
