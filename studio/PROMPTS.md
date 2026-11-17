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

## Mind Over World Short

Write a YouTube Shorts script for the Mind Over World channel.

Use the 4-step Attention Trap, in this order:
1. Stakes in the first line. Someone to root for. Something to lose. A deadline. First person. Example: "I had until 9 a.m., and I still could not sleep."
2. Big question. Can they do it? One question the viewer wants answered.
3. Head fake. Twist the ending they expect. The obvious fix fails, or the fear was never the real problem.
4. Rehook. Right after you answer one question, open a new loop. A new small question or a next step they need.

Rules:
- First-person emotional storytelling. Say "I", not "one should".
- Simple everyday English. About a 6th-grade reading level.
- ONE clear idea. Say the lesson in plain words at least once.
- About 110 to 160 words so it speaks for 45 to 75 seconds.
- Output ONE line per caption beat. After each line, add ` | ` and a suggested literal visual: the exact words, number, or name to put on screen. No metaphors. Example: `I checked it five times. | 5 times`
- If you quote a Stoic, put the quote in the line and the name after ` | — Name`.
- No swear words. No faces. No clever symbols.

Topic:
{{TRANSCRIPT}}

Return only the lines. Then, on their own lines:
TITLE: (under 70 characters)
DESCRIPTION:
TAGS:
PINNED COMMENT:

## Mind Over World long video

Write a long YouTube script for the Mind Over World channel. Aim for 6 to 10 minutes when spoken.

Use the same rules as a Mind Over World Short:
- Attention Trap shape inside the video: stakes, big question, head fake, rehook.
- First person. Simple everyday English. About a 6th-grade reading level.
- ONE clear idea. State the lesson in plain words at least once.
- Open a loop, pay it off, then open the next loop. Do not stack three lessons.
- Chapters. Start each chapter with a line that begins with `# ` and a short chapter name.
- Under each chapter, one spoken line per caption beat. After a line, add ` | ` and a literal visual (the exact words or number on screen). No metaphors.
- Stoic quotes get the name after ` | — Name`.

Topic:
{{TRANSCRIPT}}

Return:
CHAPTERS AND LINES:
TITLE:
DESCRIPTION: (2 short paragraphs)
TAGS:
PINNED COMMENT:

## Mind Over World topic ideas

Give 12 topic ideas for the Mind Over World YouTube channel.

Use Einzelgänger-style angles. Study these patterns, then write new ideas. Do not copy titles word for word.
- Pop-culture philosophy. A known character or story, then the real idea. Examples of the angle, not titles to reuse: SpongeBob, Squidward, Shawshank.
- "Why you…" pain titles. The viewer already feels the problem.
- Contrarian advice. The usual tip is wrong, and you say why in plain words.
- Short blunt commands. The shape of "Let Them Be Wrong".

For each idea return:
TITLE:
ANGLE: (one of: pop culture, why you, contrarian, command)
ONE-SENTENCE STORY:
LESSON IN PLAIN WORDS:

Keep the words simple. About a 6th-grade reading level. Stoic or practical self-improvement. No faces. One idea each.

## Mind Over World SEO

Write the YouTube upload text for a Mind Over World video.

Script:
{{TRANSCRIPT}}

Return:
TITLE: under 70 characters, clear, no fake promises. Add #shorts only if this is a Short.
DESCRIPTION: 2 short paragraphs in plain words. End with "Mind Over World".
TAGS: 10 tags, comma-separated. Include the problem people type into search, plus stoicism or the thinker's name if one is in the script.
PINNED COMMENT: one short question the viewer can answer in one line.
