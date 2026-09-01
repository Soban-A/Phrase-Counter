# Phrase Counter

Listens to your system audio (and optionally your microphone) in real time, transcribes it locally with Whisper, and counts how many times configured phrases get said — with counts synced live to a Supabase-backed web dashboard.

## How it works

1. [audio_capture.py](audio_capture.py) captures your PC's audio output via WASAPI loopback, and optionally your default microphone, mixing both into a single mono 16kHz stream.
2. [main.py](main.py) buffers a few seconds of audio at a time and hands it to [transcriber.py](transcriber.py), which transcribes it locally using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (no audio leaves your machine).
3. [phrase_matcher.py](phrase_matcher.py) fuzzy-matches the transcript against your configured phrase list.
4. On a match, [supabase_client.py](supabase_client.py) atomically increments that phrase's count in Supabase.
5. [index.html](index.html) subscribes to Supabase realtime and shows a live dashboard of the counts — hosted publicly via GitHub Pages so anyone with the link can view it.

## Prerequisites

- Windows (WASAPI loopback capture is Windows-only)
- Python 3.9+
- A free [Supabase](https://supabase.com) project

## Setup

1. **Install dependencies**

   ```
   pip install -r requirements.txt
   ```

2. **Set up the database.** Open your Supabase project → SQL Editor, and run [setup_supabase.sql](setup_supabase.sql). This creates the `phrases` table, an atomic `increment_phrase_count` function (avoids race conditions on rapid matches), and enables realtime on the table so the dashboard updates live.

3. **Configure credentials.** Copy `.env.example` to `.env` and fill in:

   ```
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_KEY=your-secret-key-here
   ```

   Get both from Supabase → Project Settings → API. Use the **secret key** (`sb_secret_...`) here — the dashboard (`index.html`) is meant to be shared publicly and is read-only via a Row Level Security policy, so `main.py` needs the secret key to bypass RLS and actually write counts. `.env` is git-ignored; never commit real credentials into `.env.example` or `index.html`.

4. **Configure phrases and audio sources** in [config.json](config.json):

   ```json
   {
     "whisper_model": "small",
     "fuzzy_threshold": 75,
     "buffer_seconds": 6,
     "capture_mic": true,
     "phrases": [
       { "id": "no_way", "name": "No Way", "phrase": "no way" }
     ]
   }
   ```

   | Setting | Description |
   |---|---|
   | `whisper_model` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large`) — bigger is more accurate but slower |
   | `fuzzy_threshold` | Minimum fuzzy-match score (0–100) to count a phrase as detected |
   | `buffer_seconds` | How much audio to accumulate before each transcription pass |
   | `capture_mic` | `true` to mix your microphone in alongside system audio, `false` for system audio only |
   | `open_dashboard` | `true` to automatically open `dashboard_url` in your browser on startup |
   | `dashboard_url` | The URL of your deployed dashboard (e.g. your GitHub Pages link) — change this if you fork the repo and deploy your own copy |
   | `silence_threshold` | Minimum RMS volume (0–1) required before a chunk is even sent to Whisper — filters out the "You" / "Thank you." hallucinations Whisper produces on silence. Raise it if that's still happening; lower it if quiet speech is getting skipped |
   | `phrases` | List of `{ id, name, phrase }` entries to track — `id` must be unique and stable (it's the database key) |

## Running

```
python main.py
```

or double-click [run.bat](run.bat). On startup it syncs your `config.json` phrases into Supabase (adding new ones, updating names/text, preserving existing counts), then starts listening and printing transcripts and matches to the console.

## Sharing the dashboard

`index.html` is deployed automatically via GitHub Pages (repo → Settings → Pages → Source: "Deploy from a branch", `main` / `(root)`) — anyone with the Pages URL can open it and watch counts update live while `main.py` is running on your machine. It only reads (via a Supabase RLS policy restricted to `SELECT`), so it's safe to share the link.

## Troubleshooting

- **`No loopback device found`** — your default playback device doesn't expose a WASAPI loopback endpoint; try switching your default output device in Windows sound settings.
- **`No default microphone found`** — set `capture_mic: false` in `config.json` if you don't want mic input, or check Windows privacy settings allow microphone access.
- **Nothing detected despite correct speech** — lower `fuzzy_threshold`, or try a larger `whisper_model`.
