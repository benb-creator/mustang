# Parula speed benchmark and screen-capture pipeline

Reproducible measurements of Parula (JMAP) against another mail app on the same computer, the same server and
the same account, recorded as real screen captures and composed into a side-by-side video:

| Comparison | OS | Left | Right |
|---|---|---|---|
| C1 | Linux | Parula, JMAP | Parula, IMAP |
| C2 | Linux | Parula, JMAP | Thunderbird, IMAP |
| C3 | Windows | Parula, JMAP | Outlook (classic), IMAP |
| C4 | Windows | Parula, JMAP | new Outlook for Windows, IMAP (synced through the Microsoft cloud) |

Tasks (`scenarios/T1.yaml` … `T7.yaml`): T1 add the account, T2 start the app, T3 open the 20,000-message
Archive, T4 search all mail for a planted term, T5 open a message with attachments, T6 jump to the oldest message,
T7 move 1,000 messages. Each scenario file holds every app's own action list; the report publishes them.

```
bench.py corpus     manifest | time | write        deterministic test corpus (30,000 messages, ~3.8 GB)
bench.py seed       import | verify | wipe         JMAP Email/import (or IMAP APPEND) into the benchmark account
bench.py snapshot   take | restore | list | server-take | server-restore
bench.py calibrate  window | points | references   window geometry, click points, reference images
bench.py env        record OS, CPU, RAM, GPU, display, app and server versions, round-trip time
bench.py run        warm-up + 5 measured runs per app and task, interleaved A B A B, with capture
bench.py analyze    settle detection per run, medians, results.json, report.md
bench.py compose    side-by-side video with labels, timers, done badges, cards, narration timeline, subtitles
bench.py encode     WebM VP9 + Opus, MP4 H.264 + AAC, YouTube master (H.264, 2160p)
bench.py verify     ffprobe checks of the encoded files
bench.py all        env, run, analyze, compose, encode, verify for one comparison
```

Every stage reads and writes files under `workdir`, so each one can be re-run on its own (`run` resumes
completed runs; `analyze --force` re-analyzes them).

## Prerequisites

Linux (C1, C2):
- An **X11 session** (Xorg). Wayland sessions can't be captured with ffmpeg `x11grab` or driven with xdotool;
  on GNOME pick "GNOME on Xorg" at login. Turn off notifications, screen saver, screen lock and automatic updates
  for the benchmark user. Fixed display resolution, 100 % scaling; 2560×1440 fits two 1280×1080 panes plus the
  marker strip.
- Python 3.10+ with `pip install -r requirements.txt` (numpy, Pillow, PyYAML, python-xlib).
- ffmpeg ≥ 7 with `x11grab`, `libx264`, `libvpx-vp9`, `libopus`, `drawtext` (freetype), `loudnorm`, `ebur128`;
  the static builds from https://github.com/BtbN/FFmpeg-Builds have all of them. `xdotool`, `taskset`
  (util-linux), the DejaVu fonts.
- Parula from the `.deb` package (no auto-updater; the AppImage updates itself). Thunderbird from the official
  tarball, extracted to `tools/thunderbird/`, with `tools/thunderbird/distribution/policies.json` =
  `{"policies": {"DisableAppUpdate": true}}`.

Windows (C3, C4), **untested** — written without access to a Windows machine:
- Python 3.10+ (`pip install -r requirements.txt`; python-xlib is skipped), ffmpeg ≥ 7 with `ddagrab`
  (gyan.dev "full" or BtbN builds), the built-in OpenSSH client for the server snapshots.
- Input goes through `SendInput` (ctypes, `benchlib/windows.py`), the sync marker is a topmost popup window,
  capture is ffmpeg `ddagrab` (Desktop Duplication) + `hwdownload`, ffmpeg's CPU affinity is set with
  `SetProcessAffinityMask`. The driver is per-monitor DPI aware; use 100 % display scaling.
- A dedicated Windows user for benchmarking: client snapshots replace that user's app data folders.

## The dedicated benchmark Stalwart instance (on the public host)

Run a separate Stalwart instance only for the benchmark, with its own data directory, so snapshots can stop,
copy and restore it without touching anything else:

1. Install the same Stalwart binary to e.g. `/opt/stalwart-bench/bin/stalwart` with its own config
   (`{"@type":"RocksDb","path":"/opt/stalwart-bench/data"}`), its own ports or its own IP, and a systemd unit
   `stalwart-bench.service` (`TimeoutStopSec=30`; Stalwart 0.16 may hang on SIGTERM, systemd then kills it,
   which RocksDB survives).
2. `touch /opt/stalwart-bench/BENCHMARK-INSTANCE`. The snapshot commands refuse to run without this file.
3. TLS certificate for the public host name (Stalwart's ACME / Let's Encrypt). Required for C4: new Outlook
   connects to IMAP accounts from the Microsoft cloud, so the server must be reachable from the internet on
   993/465 with a valid certificate.
4. DNS so that every app finds the server by itself from the email address: `autoconfig.<domain>` (Thunderbird,
   Parula) and `autodiscover.<domain>` (Outlook) pointing at the instance, plus the JMAP well-known URL. Stalwart
   serves autoconfig and autodiscover itself.
5. Raise the JMAP upload limits for seeding (defaults allow 50 MB / 1,000 uploads per user and hour, which a
   3.8 GB corpus exceeds): management object `x:Jmap` → `uploadQuota: 20000000000`, `maxUploadCount: 1000000`,
   then reload settings. Or seed with `--protocol imap` (slower: ~25 messages/s in our test).
6. Create the benchmark account (only this account is ever wiped or restored), give it a large quota, and
   disable the spam filter for it (a test mail from an unknown sender may land in Junk otherwise).
7. Allow the benchmark machine's SSH key to run the stop/start commands (`sudo systemctl stop|start
   stalwart-bench`, e.g. via a sudoers line for exactly those two commands) and to read/write
   `/opt/stalwart-bench`.

`tests/snapshot_check.py --config config.yaml` checks the setup: it takes a snapshot, changes the account
(flag, move, delete), restores, and requires the same JMAP ids, IMAP UIDs and UIDVALIDITY afterwards. With
`--protocol-level` it also tests the fallback. Both wipe and restore the benchmark account.

Snapshot methods (`server.snapshot.method`):
- `storage` (preferred): stop, copy the data dir (`cp -a --reflink=auto`), start; restore = stop, replace, start.
  Message ids, IMAP UIDs and UIDVALIDITY stay identical, so the apps' warm caches stay valid.
- `protocol` (no shell access): wipe the account (only the user named in `wipe_allowed_for`) and import the
  corpus again. Ids and UIDVALIDITY change, so client caches are invalid after every restore and the "synced"
  client snapshots can't be used; only tasks that start from a fresh client (T1) are meaningful then.

## Setup on the benchmark machine

```sh
cp config.linux.example.yaml config.yaml            # or config.windows.example.yaml; fill in the <…> values
export BENCH_ACCOUNT_PASSWORD='…'
./bench.py corpus manifest                          # work/corpus/manifest.json: counts, sizes, planted terms, digest
./bench.py seed import                              # JMAP import + verify (counts per folder, planted hit counts)
./bench.py calibrate window --app parula-jmap       # window lands exactly on display.app_region?
./bench.py calibrate window --app thunderbird
./bench.py snapshot take --name synced --apps parula-jmap,parula-imap,thunderbird
```

`snapshot take` first syncs each app from a fresh profile (with the T1 actions, or by hand with `--manual`: the
app opens, you set up the account and wait until it has synced, press Enter), takes its client snapshot, then
takes the server snapshot, then lets each app sync once more against the final server state and takes its
client snapshot again. Check in each app that the initial sync (including Thunderbird's offline download and
global search index) is complete before you continue; increase `--sync-wait` if needed.

Client profiles: Parula runs with `HOME=<workdir>/profiles/<app>/home` on Linux (its data lives in
`~/.parula` and `~/.config/Parula`, both move with `HOME`); on Windows in `%APPDATA%\Parula`. Thunderbird runs
with `-profile <dir> -no-remote` and a `user.js` that only switches off pop-ups. Outlook classic: the profile's
registry key (exported and imported with `reg`) plus its `.ost` file in `%LOCALAPPDATA%\Microsoft\Outlook`.
New Outlook keeps its cache in `%LOCALAPPDATA%\Microsoft\Olk`, but the account's sync state lives in the
Microsoft cloud and can't be restored from a snapshot: for C4, T1 starts with the account removed from new
Outlook (which also removes it from the cloud), and the other tasks start from the cache snapshot while the
cloud copy is whatever Microsoft keeps. Disclose that in the report and the video. Every restore refuses to
replace a directory that lacks the `.bench-profile` marker, so real profiles are never touched.

### Calibration

```sh
./bench.py calibrate points --app thunderbird       # move the pointer onto each named point, press Enter
./bench.py calibrate references --comparison C2     # one run per app and task with a 4 s quiet period
```

Points are stored per display layout and app relative to the app region (`work/calibration/<layout>/<app>.yaml`).
Keyboard shortcuts are used where the apps have them. Reference images (`work/references/<app>/<task>/<step>.png`)
are the settled screen of each step; afterwards a step only counts as done when the screen matches its reference
(≤ 2 % differing pixels, `reference_tolerance`), so a static "Loading…" state that lasts longer than the quiet
period isn't taken as the end. Look at the reference images once: they must show the real end state. Add
`display.masks` or per-scenario `masks` for regions that change on their own (a clock, relative dates).

## Running the comparisons

```sh
./bench.py env --comparison C2
./bench.py run --comparison C2                      # all tasks; --tasks T3,T4 for a subset
./bench.py analyze --comparison C2                  # work/results/results.json + report.md
./bench.py compose --lang en --narration voiceover/narration.en.json --variant c2-full --name c2
./bench.py encode --name c2 --lang en
./bench.py verify --name c2 --lang en
```

On Windows the same with `config.windows.example.yaml` and C3/C4. To make one video from Linux and Windows
results, copy the Windows `work/runs/C3` / `C4` and `results.json` to the Linux machine and pass both results
files: `compose --results work/results/results.json,windows-results.json`.

What a run does: restore the server snapshot and the app's client snapshot (fresh profile for T1); start the app
and bring it to the task's start state (live-only capture, not recorded); start the recording; show 5 sync markers;
for each step do its actions — the timer starts at the step's last input event — and wait until the live
low-resolution stream has been still for 1.5 s; show 5 sync markers; stop the recording; close the app. Runs are
interleaved: warm-up A, warm-up B, then A B A B … for 5 measured runs each. Failed runs are retried (up to
`runs.retries`), kept as `run-N.failed-K` and listed in the report.

### How a step is measured

- Capture: ffmpeg `x11grab` (Linux) / `ddagrab` (Windows) of the app region plus a sync-marker strip next to it,
  60 fps, lossless (`libx264rgb -qp 0 -preset ultrafast`, MKV, real per-frame timestamps), with a second
  low-resolution gray output piped to the driver for the live "settled" gate. ffmpeg is pinned to its own core.
- Clock alignment: the driver shows numbered markers (12-bit code with parity, `benchlib/marker.py`) at the start,
  at every measured input, and at the end, and logs each with the monotonic clock. The analysis finds the first
  frame showing each code and fits `video_time = a · driver_time + b`; runs whose residuals exceed 1.5 frames
  are rejected.
- Settle detection on the lossless file (`benchlib/settle.py`): per frame, the number of pixels whose largest
  channel difference to the previous frame exceeds 8; changes below 150 pixels (caret, cursor blink) and masked
  regions are ignored. A step ends at the last significant change before at least 1.0 s without one (and, with a
  reference image, only at a state that matches it). Duration = time of that frame − the logged input event
  mapped onto the video.
- Per task: the sum of its measured steps (typing between steps isn't waiting time). Reported value: the median of
  the 5 measured runs, with min and max; the video shows the median run itself (the run whose total is the median).
- User actions: every click, key press, drag, app start, and "type into a field" counts as 1 action.

Tested in a container with a synthetic app under Xvfb (`tests/e2e_fake.py`): the measured step durations matched
the app's own log of its last drawn frame within ±1 frame at 60 fps (see the test's report).

## Fairness rules (binding)

- Same computer, OS install, display resolution, window size, network, server and account snapshot. Default
  settings of each app; every deviation (e.g. update prompts or telemetry notices switched off) goes into
  `deviations` in the config and from there into the report.
- Apps are recorded one after another, never at the same time, interleaved A B A B; the video shows them side by
  side, synchronized at the start of each task, and says so in its footnote.
- Before each run, server and client state are restored from the same snapshot. One warm-up run per app and
  task is discarded (disclosed). Then 5 measured runs; the median is reported with min and max; the video shows
  the median run, never the best one.
- Screen recording runs during all measured runs of all apps; ffmpeg is pinned to its own core in the same way
  for every app.
- The environment (OS, kernel, CPU, RAM, GPU, display, app versions, Stalwart version, round-trip time, date) is
  recorded automatically and goes into the report and the result card's footnote.
- No editing beyond crop, the side-by-side layout and overlays. Waits longer than `timelapse_threshold_s` are
  shown sped up for both panes alike, labelled ("8× speed"), with the timers still showing real time.
- Every measured task goes into `results.json` and the report, including those where Parula isn't faster.

## Video, narration and audio

The composer (`benchlib/compose.py`) builds, per race: a title card (spoken `voice_before`), a countdown over both
panes' first frames, the two median runs side by side (no scaling: 1280×1080 panes on a 2560×1440 canvas), label
bars (name, version, protocol, OS) with a running timer per pane that stops at the measured end, a done badge,
the held last frame of the pane that finished first, the footnote, and the narration's supers after the race.
`fixed` segments become text cards of their `supers`; `card: result` segments become the result card (all tasks,
both apps, median times with min–max, ratio, action counts, test conditions).

Narration files follow the spec's voice-over interface (`narration.<lang>.json`): segments with the same `id`
are alternatives and the first whose `when` holds is used; placeholders `{{t.C2.left.T3}}`, `{{ratio.C2.T3}}`,
`{{actions.C2.right.T1}}`, `{{app.C2.left}}`, `{{runs}}`, `{{env.messages}}`, `{{env.archive_messages}}`,
`{{env.move_messages}}`, `{{env.search_hits}}`, `{{env.C2.date|os|cpu|ram|display|server|rtt_ms|cloud_sync_confirmed}}`
are filled from `results.json` (German number format for `de`). `--variant <name>` takes the segment list from
`variants/variants.json` next to the narration file.

Voice: compose writes `voice-script.md/json` with the final texts (after the measurements are known). Record or
synthesize them as `voice/<lang>/<segment-id>.wav` (`fixed`, `card`) and `<segment-id>.before.wav`,
`.during.wav`, `.after.wav` (race parts), then compose again: the timeline uses the real lengths. A
`voice_during` that is longer than the faster app's time is dropped. Optional music bed (`compose.music`) is
ducked under the voice. Outputs per video: `master.mkv` (lossless RGB), `audio.wav`, `timeline.json`,
`subtitles.vtt`, `subtitles.srt`.

Encoding converts once from RGB to BT.709 limited-range 4:2:0 and tags it: WebM (VP9 2-pass CRF 30, row-mt,
`tune-content=screen`, Opus 160k), MP4 (H.264 High CRF 18, +faststart, AAC 192k), YouTube master (H.264 CRF 12,
lanczos upscale to 2160p, AAC 384k). Audio is normalized to −14 LUFS integrated, −1 dBTP (two-pass loudnorm).
`verify` checks codecs, 60 fps, duration, color tags, faststart and loudness.

## Publishing the results

Publish together with the video (e.g. on parula.app/speedtest, linked from the video description):
`results.json`, `report.md`, the scenario files, the config without secrets, the corpus manifest (seed, counts,
digest), the environment records, and this code. Anyone can regenerate the identical corpus from the seed.

## Tests

```sh
python -m pytest tests/test_units.py                       # settle detection, clock fit, median run, narration,
                                                           # scenarios, corpus determinism and file validity
tests/e2e_fake.py --work /tmp/e2e --tools <dir with ffmpeg, Xvfb, xdotool>
tests/snapshot_check.py --config config.yaml [--protocol-level]
```
