# Third-party licenses

mowtion itself is MIT. See `LICENSE`.

The pieces below are not all MIT. They are free to use. None of them is Remotion.
mowtion does not depend on Remotion, and the renderer is ordinary Python drawing code.

## Bundled in this repository

These fonts are shipped under `src/mowtion/assets/fonts/` so a render looks the same
on every computer. The license text is `src/mowtion/assets/fonts/OFL.txt`.

| Work | License |
| --- | --- |
| Inter (Regular, Medium, SemiBold, Bold) | SIL Open Font License 1.1 |
| JetBrains Mono (Regular, Bold) | SIL Open Font License 1.1 |
| Instrument Serif (Regular, Italic) | SIL Open Font License 1.1 |

## Installed with pip (not copied into the git tree)

| Project | License | What it does here |
| --- | --- | --- |
| [NumPy](https://numpy.org/) | BSD-3-Clause | Audio arrays |
| [SciPy](https://scipy.org/) | BSD-3-Clause | Resampling and synth filters |
| [soundfile](https://github.com/bastibe/python-soundfile) | BSD-3-Clause | WAV read and write. Wheels include libsndfile (LGPL-2.1). |
| [Pillow](https://python-pillow.org/) | MIT-CMU (HPND-style) | Drawing the frames |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | Word-level transcription |
| [CTranslate2](https://github.com/OpenNMT/CTranslate2) | MIT | Whisper runtime |
| [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | MIT | Kokoro TTS runtime |
| [ONNX Runtime](https://onnxruntime.ai/) | MIT | Runs the Kokoro model |
| [phonemizer](https://github.com/bootphon/phonemizer) | GPL-3.0 | Turns text into phonemes for Kokoro |
| [espeak-ng](https://github.com/espeak-ng/espeak-ng) | GPL-3.0 | Phoneme engine used by phonemizer. `espeakng-loader` ships a build of it inside the Python wheel. |
| [huggingface_hub](https://github.com/huggingface/huggingface_hub) | Apache-2.0 | Downloads the Whisper model on first run |

`phonemizer` and `espeak-ng` are GPL-3.0. They are pulled in only because Kokoro
needs a phonemizer. They are not copied into this repository. If you distribute
a build that includes those libraries, follow the GPL-3.0 terms for that part
of the bundle. The rest of mowtion stays MIT.

## Downloaded on first run (not in git, not in the installer)

| Work | License | Where it goes |
| --- | --- | --- |
| Kokoro-82M ONNX weights (`kokoro-v1.0.onnx`, `voices-v1.0.bin`) | Apache-2.0 | `~/.cache/mowtion/models/` |
| OpenAI Whisper `small.en` (via faster-whisper) | MIT | `~/.cache/mowtion/models/whisper/` |

Model files come from the Kokoro ONNX release and from Hugging Face the first
time you render. They are not part of the source tarball.

## Not bundled, must be installed separately

| Tool | License | Notes |
| --- | --- | --- |
| [FFmpeg](https://ffmpeg.org/) | LGPL-2.1 or GPL, depending on the build you install | Used to decode input, master loudness, and encode H.264 + AAC. mowtion does not ship an ffmpeg binary. Install an LGPL build if you want to avoid GPL. |

## Explicitly not used

Remotion is not a dependency. Its license is not free for every use, so the
motion graphics are drawn here with Pillow instead.
