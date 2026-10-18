# Parula speed benchmark and screen-capture pipeline

Reproducible measurements of Parula (JMAP) against another mail app on the same computer, the same server and
the same account, recorded as real screen captures and composed into short side-by-side videos:

| Comparison | OS | Left | Right |
|---|---|---|---|
| C1 | Linux | Parula, JMAP | Parula, IMAP |
| C2 | Linux | Parula, JMAP | Thunderbird, IMAP |
| C3 | Windows | Parula, JMAP | Outlook (classic), IMAP |
| C4 | Windows | Parula, JMAP | new Outlook for Windows, IMAP (synced through the Microsoft cloud) |

The first videos have one task, the same in all four tests: **T1, a new account in the app until its Inbox lists
all 30,000 messages** (corpus profile `inbox-30k`). The other tasks (`scenarios/T2.yaml` … `T7.yaml`: start the app,
open the 20,000-message Archive, search, open a message with attachments, jump to the oldest message, move 1,000
messages) stay available with the corpus profile `multi-folder`. Each scenario file holds every app's own action
list; the report publishes them.

```
bench.py corpus     manifest | time | write        deterministic test corpus (profile inbox-30k or multi-folder)
bench.py seed       import | verify | wipe         JMAP Email/import (or IMAP APPEND) into the benchmark account
bench.py snapshot   take | restore | list | server-take | server-restore
bench.py calibrate  window | points | references | crop   window, click points and regions, reference images
bench.py env        record OS, CPU, RAM, GPU, display, app and server versions, round-trip time
bench.py run        warm-up + 5 measured runs per app and task, interleaved A B A B, with capture
bench.py analyze    settle detection and checks per run, medians, results.json, report.md
bench.py compose    short video: hook, "Go!", race, hold, cards, narration timeline, subtitles, audio
bench.py voice      text-to-speech for the lines the composition chose
bench.py method     method texts below the video (YouTube description, website expander), EN and DE
bench.py encode     WebM VP9 + Opus, MP4 H.264 + AAC, YouTube master (H.264, 2160p), publication gate
bench.py verify     ffprobe checks of the encoded files
bench.py all        env, run, analyze, compose, encode, verify for one comparison
```

Every stage reads and writes files under `workdir`, so each one can be re-run on its own (`run` resumes
completed runs; `analyze --force` re-analyzes them).

## Prerequisites

Linux (C1, C2):
- An **X11 session** (Xorg). Wayland sessions can't be captured with ffmpeg `x11grab` or driven with xdotool;
  on GNOME pick "GNOME on Xorg" at login. Turn off notifications, screen saver, screen lock and automatic updates
  for the benchmark user. Fixed display resolution 2560×1440, 100 % scaling: two 1280×940 app windows plus the
  bands above and below them fill a 2560×1440 video. Close every other app during the runs.
- Python 3.10+ with `pip install -r requirements.txt` (numpy, Pillow, PyYAML, python-xlib).
- ffmpeg ≥ 7 with `x11grab`, `libx264`, `libvpx-vp9`, `libopus`, `drawtext` (freetype), `loudnorm`, `ebur128`;
  the static builds from https://github.com/BtbN/FFmpeg-Builds have all of them. `xdotool`, `taskset`
  (util-linux), the DejaVu fonts.
- **Parula from the `.deb` package** (`sudo apt install ./parula_<version>_amd64.deb`, installs to `/opt/Parula`;
  no auto-updater, unlike the AppImage). Thunderbird from the official tarball, extracted to
  `tools/thunderbird/`, with `tools/thunderbird/distribution/policies.json` = `{"policies": {"DisableAppUpdate": true}}`.

Windows (C3, C4), **untested** — written without access to a Windows machine:
- Python 3.10+ (`pip install -r requirements.txt`; python-xlib is skipped), ffmpeg ≥ 7 with `ddagrab`
  (gyan.dev "full" or BtbN builds), the built-in OpenSSH client for the server snapshots and the server log.
- Input goes through `SendInput` (ctypes, `benchlib/windows.py`), the sync marker is a topmost popup window,
  capture is ffmpeg `ddagrab` (Desktop Duplication) + `hwdownload`, ffmpeg's CPU affinity is set with
  `SetProcessAffinityMask`. The driver is per-monitor DPI aware; use 100 % display scaling. Before every key or
  typed text the driver checks that the app's window is in the foreground (it brings it there with
  `AttachThreadInput` + `SetForegroundWindow`); if that fails, the run fails and nothing is typed.
- A dedicated Windows user for benchmarking: client snapshots replace that user's app data folders.

## The dedicated benchmark Stalwart instance (on the public host)

Run a separate Stalwart instance only for the benchmark, with its own data directory, so snapshots can stop,
copy and restore it without touching anything else:

1. Install the same Stalwart binary to e.g. `/opt/stalwart-bench/bin/stalwart` with its own config
   (`{"@type":"RocksDb","path":"/opt/stalwart-bench/data"}`), its own ports or its own IP, and a systemd unit
   `stalwart-bench.service` (`TimeoutStopSec=30`; Stalwart 0.16 may hang on SIGTERM, systemd then kills it,
   which RocksDB survives).
2. `touch /opt/stalwart-bench/BENCHMARK-INSTANCE /opt/stalwart-bench/data/BENCHMARK-DATA`. Snapshot and restore
   refuse to run without both files, when `data_dir` or `snapshot_dir` lies outside `instance_dir` (checked
   before and, after resolving symlinks, on the server), when the stop command fails, or when a process of the
   instance is still running after it (`running_check`, default: a `stalwart` process whose command line names
   `instance_dir`, i.e. its binary or config file lies there; set your own check, e.g. `systemctl is-active
   --quiet stalwart-bench`, if the instance runs in a container). Nothing is changed in those cases.
3. TLS certificate for the public host name (Stalwart's ACME / Let's Encrypt). Required for C4: new Outlook
   connects to IMAP accounts from the Microsoft cloud, so the server must be reachable from the internet on
   993/465 with a valid certificate.
4. DNS so that every app finds the server by itself from the email address: `autoconfig.<domain>` (Thunderbird,
   Parula) and `autodiscover.<domain>` (Outlook) pointing at the instance, plus the JMAP well-known URL. Stalwart
   serves autoconfig and autodiscover itself.
5. Raise the JMAP upload limits for seeding (defaults allow 50 MB / 1,000 uploads per user and hour, which the
   corpus exceeds): management object `x:Jmap` → `uploadQuota: 20000000000`, `maxUploadCount: 1000000`,
   then reload settings. Or seed with `--protocol imap` (slower: ~25 messages/s in our test).
6. Create the benchmark account (only this account is ever wiped or restored), give it a large quota, and
   disable the spam filter for it (a test mail from an unknown sender may land in Junk otherwise).
7. Allow the benchmark machine's SSH key to run the stop/start commands (`sudo systemctl stop|start
   stalwart-bench`, e.g. via a sudoers line for exactly those two commands), to read/write `/opt/stalwart-bench`
   and to read its log directory.
8. The **evidence log** (next section).
9. **Password rotation:** `server.password_rotation` (an administrator of the benchmark instance, password from
   an environment variable) gives the test account a new random password of the same length after every
   restore, through Stalwart's management API (`x:Account/set`); the driver types that password. A password an
   app or a cloud service kept from an earlier run then fails, and its login attempts appear in the server log
   as failed logins. The password in `account.password_env` is the one in the snapshots (seeding, checks).
10. For C4 only: put Microsoft's network prefixes (the evidence lists them, e.g. AS8075's) on the instance's
   `x:AllowedIp` list during the C4 series, so Stalwart's ban after failed logins doesn't block Microsoft's
   retries with an old password (they are part of the evidence); remove them afterwards.

`tests/snapshot_check.py --config config.yaml` checks the setup: it takes a snapshot, changes the account
(flag, move, delete), restores, and requires the same JMAP ids, IMAP UIDs and UIDVALIDITY afterwards. With
`--protocol-level` it also tests the fallback. Both wipe and restore the benchmark account.

Snapshot methods (`server.snapshot.method`):
- `storage` (preferred): stop, copy the data dir (`cp -a --reflink=auto`), start; restore = stop, replace, start.
  Message ids, IMAP UIDs and UIDVALIDITY stay identical, so the apps' warm caches stay valid.
- `protocol` (no shell access): wipe the account (only the user named in `wipe_allowed_for`) and import the
  corpus again. Ids and UIDVALIDITY change, so client caches are invalid after every restore and the "synced"
  client snapshots can't be used; only tasks that start from a fresh client (T1) are meaningful then.

### Server log evidence (who logged in from where, what each source fetched)

Every run collects the benchmark server's log for its time window: every login with its source address and the
account that authenticated, every IMAP/POP fetch (which messages, whether the full content was fetched) and every
JMAP download, per source address. Each address that isn't the benchmark computer is looked up (RDAP at
rdap.org for the registrant, RIPEstat for the origin AS, e.g. AS8075 Microsoft). This is the evidence behind the
C4 statements (new Outlook's sync logs in from Microsoft's networks with the account's password and copies the
messages) and behind "Parula connects directly" in all tests (all its logins come from the benchmark computer).

Stalwart 0.16 logs these events (checked on 0.16.26 with a direct IMAP client) only at debug level, so add a
second, small log tracer that writes just them (management API as admin, then restart the instance):

```json
["x:Tracer/set", {"create": {"ev": {"@type": "Log", "path": "/opt/stalwart-bench/logs", "prefix": "evidence",
  "level": "debug", "ansi": false, "multiline": false, "lossy": false, "eventsPolicy": "include",
  "events": {"auth.success": true, "auth.failed": true, "imap.connection-start": true, "imap.connection-end": true,
             "imap.select": true, "imap.fetch": true, "imap.logout": true, "pop3.connection-start": true,
             "pop3.fetch": true, "http.request-url": true, "smtp.connection-start": true}}}}, "0"]
```

Stalwart keeps its settings in the data directory, so a snapshot restore also restores the tracer setup: add the
tracer **before** taking the snapshots (`seeded`, `synced`), or take them again afterwards.

Lines look like `2026-10-18T20:37:11Z INFO Authentication successful (auth.success) listenerId = "imap", …,
remoteIp = 203.0.113.7, …, accountName = "bench@example.org"` and `… (imap.fetch) … remoteIp = …,
documentId = [2001, 2002], details = ["Uid", "BodySection { peek: true, sections: [], partial: None }"]`
(`sections: []` = the whole message; `[Header]` = headers only). The log has no byte counts: sizes come from one
JMAP `Email/get` (Stalwart's JMAP email ids encode the same document id). Config: `server.log.path`
(`/opt/stalwart-bench/logs/evidence.*`), read over `server.snapshot.ssh`. The benchmark computer's address as the
server sees it is found by a probe request with a unique path at the start of each `run` (or set
`server.log.benchmark_ips`). The evidence: `runs/<C>/<T>/<app>/<run>/evidence.json` (and `server-log.txt`),
summarized per comparison in `results.json` (`evidence`) and the report. The summaries name networks (owner,
ASN, prefix), never single addresses, and never the benchmark computer's address; the raw lines stay in the run
directory.

## Setup on the benchmark machine

```sh
cp config.linux.example.yaml config.yaml            # or config.windows.example.yaml; fill in the <…> values
export BENCH_ACCOUNT_PASSWORD='…'
./bench.py corpus manifest                          # work/corpus/manifest.json: counts, sizes, digest
./bench.py seed import                              # JMAP import + verify (counts, attachments, planted terms)
./bench.py snapshot server-take --name seeded       # T1 starts every run from this server state
./bench.py calibrate window --app parula-jmap       # window lands exactly on display.app_region?
./bench.py calibrate window --app thunderbird
```

Client profiles: Parula runs with `HOME=<workdir>/profiles/<app>/home` on Linux (its data lives in
`~/.parula` and `~/.config/Parula`, both move with `HOME`); the user's GTK and font settings are linked into that
home and the font cache stays the user's (`XDG_CACHE_HOME`), so Parula looks and starts like Thunderbird, which
runs with the real `HOME`. Lingering Parula processes are found by binary path *and* the benchmark `HOME`, never
your own Parula. Thunderbird runs with `-profile <dir> -no-remote` and a `user.js` that switches off its start
page (the one deviation from its defaults that changes what it does: no web page loads during the measurement)
and pop-ups. Neither app keeps the password in the desktop keyring. Outlook classic: the profile's registry key
and `Office\16.0\Outlook\Setup` (exported and imported with `reg`) plus its `.ost` file; the fresh state is an
empty `Bench` profile, so `/profile Bench` opens the account setup; list its Credential Manager entries in
`credential_targets` (check `cmdkey /list` after one setup). New Outlook: see "New Outlook (C4)". Every restore
refuses to replace a directory that lacks the `.bench-profile` marker, so real profiles are never touched.

For T2–T7 (`multi-folder` corpus): `snapshot take --name synced --apps …` syncs each app from a fresh profile,
then checks that the sync is complete: the screen is still, the profile size stops changing for
`snapshot.stable_min` minutes and, with the server log, the app fetches nothing for that long; the app must quit
by itself before its profile is copied. The check is recorded in `snapshots/<name>/meta.json`.

### Calibration

```sh
./bench.py calibrate points --app thunderbird --tasks T1     # each point, then each region's two corners
./bench.py calibrate references --comparison C2 --tasks T1   # one run per app with long quiet periods
```

`calibrate points` asks for every point (button, field) and region of the app's scenarios; with
`--points button.continue,protocol.imap` only for those, so you can bring the app to the page that shows them
first (T1's setup pages appear one after another: calibrate one page, click on, calibrate the next).
Points and regions are stored per display layout and app relative to the app region
(`work/calibration/<layout>/<app>.yaml`).

T1's completion checks, per app (`scenarios/T1.yaml`):
- `regions` (e.g. `inbox.count`, the Inbox's message count in the folder pane, or another area that only shows
  its final state when all messages are listed): the step only ends at a frame where each region matches the
  calibration run's final state, and any change inside a region counts as a screen change, however small. An app
  that shows its first page early and loads the rest of the list in the background is therefore measured until
  the list is complete, not until the first page appears.
- `verify`: after the measured end, End jumps to the end of the list, and within 3 s `list.bottom` must show what
  it showed in the calibration run (the corpus's oldest message). It is not waiting time and not a user action.
  If it fails, the app did not list all messages at the measured end: the run counts as a differing result
  (status 3).
- `first_visible` (`list.top`): the time the first rows appear, reported as "first messages visible".
- `after_end: fail`: a significant screen change after the measured end makes the run invalid.

`calibrate references` makes, per step, `references/<app>/<task>/<step>.png` (full frame), `<step>@<region>.png`,
`<step>.first@<region>.png` and `<step>.verify@<region>.png`. **Look at every reference image once**: it must show
the real end state (all messages listed, the oldest message at the bottom). A step whose reference is missing
fails its analysis (set `expect: none` to measure a step without one). `calibrate crop --run <run dir> --at
<seconds> --app <id> --region <name> --kind opening` saves a region of a recorded frame, e.g. a Microsoft app's
opening screen (`opening_screen` in the scenario), which the video then hides behind a neutral card.

Add `display.masks` or per-scenario `masks` for regions that change on their own (a clock, relative dates); the
report lists every mask, region and setting per app and step.

## First videos (T1), command by command

```sh
# Linux, C1 and C2 (config with corpus.profile inbox-30k and tasks [T1])
./bench.py env --comparison C2
./bench.py run --comparison C2 --tasks T1           # 1 warm-up + 5 measured runs per app, A B A B
./bench.py analyze --comparison C2                  # work/results/results.json, report.md, facts.json template
# set the person-checked facts in work/results/facts.json (see below)
./bench.py compose --narration <voiceover dir> --variant c2 --lang en --name c2
./bench.py voice --name c2 --lang en                # text-to-speech for exactly the chosen lines
./bench.py compose --narration <voiceover dir> --variant c2 --lang en --name c2   # again, with the real lengths
./bench.py method --narration <voiceover dir> --variant c2 --lang en --name c2    # YouTube text + expander
./bench.py encode --name c2 --lang en
./bench.py verify --name c2 --lang en
```

`run --comparison C2` records the whole session of its computer (`sessions.linux`: Parula JMAP, Parula IMAP,
Thunderbird, interleaved A B C A B C), so C1 and C2 use the same Parula runs and `analyze` writes both comparisons.
The same with `--lang de`, and for C1 (`--variant c1`). On Windows the same with `config.windows.example.yaml`
for C3 and C4. The combined cut merges both machines' results: copy the Windows `work/runs/C3`, `C4` and
`results.json` to the Linux machine and pass both files (`compose --results work/results/results.json,
windows-results.json --variant combined`); merging refuses results whose run counts or corpus differ. The
narration files, `variants/variants.json`, `variants/compose.json` and the method templates come from the
voice-over directory (`--narration <dir>`).

### Facts set by a person (`work/results/facts.json`)

`analyze` creates the template; the pipeline never fills it. Per comparison:
`right_protocol_default: 1` after checking our own T1 recording that the right-hand app's own account setup chose
IMAP for this server; for C4 also `cloud_sync_confirmed: 1` (new Outlook's setup screen in our recording says the
account syncs through the Microsoft cloud), `dialog_text` (that screen's text, typed from the recording) and
`microsoft_footage: 1` once a lawyer confirmed Microsoft's screenshot permission covers the C4 footage.
The server-log facts (`left_direct_only`, `cloud_login_confirmed`, `cloud_fetched_messages`, …) come from the
evidence.

### New Outlook (C4)

New Outlook syncs IMAP accounts through the Microsoft cloud, so its state can't be restored from a snapshot.
Every C4 run of new Outlook is a new account setup: its `finish` sequence (scenario T1) removes the account with
"remove from all devices" (also from the Microsoft cloud) and then waits until the server log shows no login from
outside the benchmark computer for 10 minutes (`wait_cloud_quiet`); the logins seen in that time are recorded
(`cloud_logins_after_removal`). If the removal fails, the series stops, because the next run would not be a new
setup. After the last run, `server.log.final_watch_min` keeps watching the log and records later Microsoft logins
(`evidence/<C>/<T>/after-series.json`). The procedure is listed in the report and the method text.

Before the removal, the account stays in new Outlook until the server log shows no fetch from outside the test
computer for 3 minutes (at most 2 hours; not measured time), so the evidence covers everything Microsoft fetched.
Full-content and header-only fetches are counted separately (`cloud_fetched_messages`, `cloud_fetched_headers`),
login attempts after the removal include failed ones (`cloud_logins_after_removal`).

Every variant may only be published when its `publish_when` in `compose.json` holds (C4:
`cloud_sync_confirmed`, `cloud_login_confirmed`, `left_direct_only`; the combined cut also one session per
computer). `encode` refuses otherwise and names the first variant of its `publish_instead` chain whose own
condition holds (e.g. `c4-direct`), or none; `encode --internal-preview` makes a copy marked "not for publication"
for review. In variants with the data-path card, new Outlook's pane shows footage only when
`c4_microsoft_footage_when` holds (`microsoft_footage` in `facts.json`), otherwise a neutral timer card.

## What a run does

Restore the server snapshot (`seeded` for T1) and the app's client snapshot (fresh profile for T1); start the app
and bring it to the task's start state (live-only capture, not recorded); start the recording; show 5 sync markers;
for each step do its actions — the timer starts at the step's last input event; after a click the pointer moves
out of the recorded area — and wait until the live low-resolution stream has been still for `quiet_s` (the same
quiet period the analysis uses) and matches the step's references; run the step's verify actions; show 5 sync
markers; record the scenario's tail (T1: 30 s, to show what the app does after the list is complete); show 5
markers; stop the recording; run the finishing sequence; close the app; collect the server log of the run.

Runs are interleaved: warm-up A, warm-up B, then A B A B … for 5 measured runs each. Each run is analyzed right
after it is recorded (`runs.analyze_after_each`). A run that failed for a technical reason (window not found,
capture error, crash, no screen reaction to an input, sync markers that don't fit, dropped frames inside a measured
step, the live gate moving on before the completion check matched) is recorded again **at the end of the series**,
at most `runs.retries` times, kept as `run-N.failed-K` and listed in the report. A run that reaches the time limit
(`timeout_s` of the scenario, T1: 2 hours) is a measurement ("not done within the limit") and is never recorded
again; so is a differing result.

### How a step is measured

- Capture: ffmpeg `x11grab` (Linux) / `ddagrab` (Windows) of the app region plus a sync-marker strip next to it,
  60 fps, lossless (`libx264rgb -qp 0 -preset ultrafast`, MKV, real per-frame timestamps), without the pointer,
  with a second low-resolution gray output piped to the driver for the live "settled" gate. ffmpeg is pinned to
  its own core.
- Clock alignment: the driver shows numbered markers (12-bit code with parity, `benchlib/marker.py`) at the start,
  at every measured input, and at the end, and logs each with the monotonic clock. The analysis finds the first
  frame showing each code and fits `video_time = a · driver_time + b`; runs whose residuals exceed 1.5 frames
  fail. Frame times come from the decoder (ffmpeg `showinfo`), so a frame it skips can't shift the later ones.
- Settle detection on the lossless file (`benchlib/settle.py`): per frame, the number of pixels whose largest
  channel difference to the previous frame exceeds 8; changes below 150 pixels (caret, cursor blink) and masked
  regions are ignored, except inside the step's check regions, where every change counts; slow fades are found
  by comparing with the frame 6 frames earlier. A step ends at the last significant change before at least
  `quiet_s` without one, at a frame that matches the step's references and regions. Duration = time of that frame
  − the logged input event mapped onto the video. Missing frames inside a measured step (a gap of more than
  `max_gap_frames`, or more than 2 frame intervals before the end frame) fail the run.
- Per task: the sum of its measured steps (typing between steps isn't waiting time). Reported value: the median of
  the 5 measured runs (a run that reached the limit counts as larger than every measured one), with min and max;
  the video shows the median run itself.
- Status per app and task: 0 valid median; 1 no valid median (fewer than 5 valid or timed-out runs, or the app
  version changed during the series); 2 the median is at the time limit; 3 a measured run showed a differing
  result. The report gives the reason.
- User actions: every click, key press, drag, app start, and "type into a field" counts as 1 action.

Tested in a container with a synthetic app under Xvfb (`tests/e2e_fake.py`): the measured step durations matched
the app's own log of its last drawn frame within ±1 frame at 60 fps; without its completion region, the step whose
list keeps loading in the background would have ended 1.2–2.0 s too early.

## Fairness rules (binding)

- Same computer, OS install, display resolution, window size, network, server and account snapshot. Default
  settings of each app; every deviation goes into `deviations` in the config and from there into the report and
  the method text; procedures (e.g. the account removal in new Outlook) into `procedures`.
- Apps are recorded one after another, never at the same time, interleaved A B A B; the video shows them side by
  side, synchronized at the start of each task, and says so in its footnote. If the panes would finish on screen
  in another order than their timers stop (typing between the setup steps), each pane shows only its waiting
  periods back to back and the footnote says "typing cut out".
- Before each run, server and client state are restored from the same snapshot. One warm-up run per app and
  task is discarded (disclosed). Then 5 measured runs; the median is reported with min and max; the video shows
  the median run, never the best one.
- Screen recording runs during all measured runs of all apps; ffmpeg is pinned to its own core in the same way
  for every app.
- The environment (OS, kernel, CPU, RAM, GPU, display, app versions per run, Stalwart version, round-trip time,
  date) is recorded automatically and goes into the report and the method text.
- No editing beyond crop, the side-by-side layout and overlays (all outside the app panes). Waits beyond the race
  budget are shown as a labelled time-lapse with one factor for both panes (the label stays, in the past tense,
  until the end of the hold); the timers show real time. Microsoft
  panes: the complete window, no held frame (a finished pane keeps playing its recorded tail), and beyond the
  budget a timer race with neutral cards unless `microsoft_timelapse` is set after a lawyer's OK.
- Every measured task goes into `results.json` and the report, including those where Parula isn't faster.

## Video, narration and audio

`compose` follows the voice-over's interface (`narration.<lang>.json`, `variants/variants.json`,
`variants/compose.json`): segments with the same `id` are alternatives and the first whose `when` holds is used
(comparisons with a missing or text value are false); placeholders (`t.*`, `time.*`, `tmin.*`, `tmax.*`,
`status.*`, `ratio.*`, `actions.*`, `app.*`, `env.*` incl. the C4 evidence, `runs`, `time.limit`) are filled from
`results.json`, the environment records, the evidence and `facts.json` (German number format for `de`). A voice
line that would speak a missing value stops the composition. A race: the hook (`voice_before` over both panes'
first frames, title, label bars), "Go!" (0.8 s, `countdown-go.wav`), the race (real time up to the race budget,
then one time-lapse factor), the hold (both times, the supers, `voice_after`); the narration's two-line `footnote`
from the hook to the end of the hold. Failed or differing results show a neutral card instead of race footage;
time limits run the race to the limit with "Time limit reached". The composition checks that the panes finish on
screen in the order their timers stop and that the variant's length is within `video_length_s`.

`bench.py voice` synthesizes exactly the lines in `voice-script.json` (the chosen alternatives) into
`voice/<lang>/`, with `compose.json`'s `voice_direction` per segment (speaking rate; pauses go before the last
sentences), with the engine in `speech.<lang>`: a local command (e.g. Piper, model pinned by SHA-256) or Google
Cloud Text-to-Speech (key from an environment variable); the engine and voice go into `voice/<lang>/credit.json`
and from there into the method text. Optional music (`compose.music`, with `compose.music_license`: title,
author, license, URL, Content ID status — required) is ducked under the voice and faded out at the end; optional
start and finish sounds (`sfx_start`, `sfx_finish`) are the same for both panes. Outputs per video: `master.mkv`
(lossless RGB), `audio.wav`, `timeline.json`, `subtitles.vtt`, `subtitles.srt`, `voice-script.md/json`.

`bench.py method` renders the voice-over's method templates (`method/<variant>.<lang>.youtube.txt` and
`.expander.md`) with every run in run order, the action lists, the server-log evidence, the deviations, what each
app kept doing after the list was complete, and `publish.page_url`, `repo_url`, `imprint_url`; it fails on a
missing value (`--allow-missing` for drafts) and when the YouTube text exceeds 5,000 bytes (UTF-8) or contains
`<` or `>`. The expander is written as Markdown and HTML.

Encoding converts once from RGB to BT.709 limited-range 4:2:0 and tags it: WebM (VP9 2-pass CRF 30, row-mt,
`tune-content=screen`, Opus 160k), MP4 (H.264 High CRF 18, +faststart, AAC 192k), YouTube master (H.264 CRF 12,
lanczos upscale to 2160p, AAC 384k). Audio is normalized to −14 LUFS integrated, −1 dBTP (two-pass loudnorm).
`verify` checks codecs, 60 fps, duration, color tags, faststart and loudness.

## Publishing

The method goes directly below the video: on YouTube into the description (`method/<variant>.<lang>.youtube.txt`),
on parula.app into an expander below the video (`.expander.html`). Publish with it, e.g. in the repository:
`results.json`, `report.md`, the evidence summaries, the scenario files, the config without secrets, the corpus
manifest (seed, counts, digest), the environment records, and this code. Anyone can regenerate the identical
corpus from the seed.

## Tests

```sh
python -m pytest tests/                                     # settle detection incl. completion regions, fades,
                                                           # gaps; clock fit; censored medians and statuses;
                                                           # snapshot guards; server-log parsing and evidence;
                                                           # narration, spoken durations, method templates,
                                                           # speech; corpus profiles and determinism
BENCH_VOICEOVER=<voice-over dir> python -m pytest tests/   # also every real variant and method template
tests/e2e_fake.py --work /tmp/e2e --tools <dir with ffmpeg, Xvfb, xdotool>
tests/snapshot_check.py --config config.yaml [--protocol-level]
```
