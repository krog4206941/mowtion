# Prompts for free Grok or ChatGPT

Copy one prompt. Paste it into free Grok or ChatGPT.

In the app, the Copy button fills in the transcript, the date, and the link for you.
If you copy from this file by hand, replace each `{{TOKEN}}` yourself.

`{{TRANSCRIPT}}` the words with times
`{{DATE}}` the day the footage was posted
`{{TODAY}}` today's date
`{{SOURCE}}` the channel or event name
`{{URL}}` the normal public link
`{{TITLE}}` the video title

## Find the best clip

You are helping a video editor pick ONE moment from a transcript.

Goal: choose the best 90 to 120 second stretch. It should stand alone. It should have one clear idea, a strong opening line, and a strong ending line. Do not start or end in the middle of a sentence.

Return ONLY this:

START: hh:mm:ss.xx
END: hh:mm:ss.xx
WHY: one sentence
HOOK IDEA: one short line
OPENING LINE: the first sentence of the clip
CLOSING LINE: the last strong sentence of the clip

Rules:
- Start and end must match timestamps that are in the transcript.
- The length must be between 90 and 120 seconds.
- If the whole transcript is shorter than 90 seconds, use the whole thing and say so.
- Do not invent words that are not in the transcript.

TRANSCRIPT:
{{TRANSCRIPT}}

## Write the hook

Write the on-screen titles for a short video.

Use simple words. No hashtags. No emojis. Short lines. The hook is the first thing on screen.

Return:
HOOK LINE 1:
HOOK LINE 2:
HEADLINE:
SUBTITLE:
END LINE 1:
END LINE 2:

HOOK LINE 1 and HOOK LINE 2 are big. About 2 to 5 words each.
HEADLINE is one line, about 8 words, for the top of the video.
SUBTITLE is one short sentence under the headline.
END LINE 1 and END LINE 2 are the last screen. Very short.

Topic or transcript:
{{TRANSCRIPT}}

## Write the X post

Write an X post in the style of @XFreeze and @cb_doge.

Use original wording. Do not copy their posts. Be favorable to Elon Musk. Do not attack him. Do not add facts that are not in the transcript.

Footage date: {{DATE}}
Today's date: {{TODAY}}
Source name: {{SOURCE}}
Source URL: {{URL}}
Video title: {{TITLE}}

Transcript:
{{TRANSCRIPT}}

How to open the post:
- If the footage is 7 days old or newer, you may open with "Elon Musk just revealed..."
- Use "BREAKING:" only if the footage is 48 hours old or newer.
- If the footage is older than 7 days, open with "Elon Musk on..." or "Elon Musk explains..."
- Never use "just revealed" or "BREAKING" for old footage.

Shape of the post:
- Short lines.
- Use numbers when the transcript has numbers.
- Bullet facts. Start each fact with a bullet.
- A strong closing line.
- Then a source credit line with the date and a normal public URL. Use the full https link. Do not use a short link.
- 1 or 2 hashtags.
- Then two more ways to open the post, labeled ALT HOOK 1 and ALT HOOK 2.

Keep it easy to read on a phone.

## Write a YouTube Short

Write a YouTube Shorts script for the Mind Over World channel.

Use the Attention Trap method, in this order:
1. First line: the stakes. Say what the viewer loses or risks if they skip. One short sentence.
2. Big question: one question they want answered.
3. Head fake: start toward the obvious answer, then turn. The real idea is not the obvious one.
4. Rehook: one line that pulls them back before the payoff.
5. Payoff: the one idea, in plain words.
6. Last line: a short closer they can remember.

Rules:
- Simple English. About a 6th-grade reading level.
- One clear idea only. Do not add a second lesson.
- 70 to 110 words. About 30 to 45 seconds when spoken.
- Write the visuals as literal shots. Say what the camera shows. Example: "Show a phone face-down on a table." Do not say "show something inspiring."
- No swear words. No jargon.

Also write the SEO pack:
- TITLE: under 60 characters, clear, no fake promises
- DESCRIPTION: 2 short sentences, then the source line if a source is given
- TAGS: 8 to 12 tags, separated by commas

Topic or transcript:
{{TRANSCRIPT}}

Return:
SPOKEN SCRIPT:
VISUALS:
TITLE:
DESCRIPTION:
TAGS:
