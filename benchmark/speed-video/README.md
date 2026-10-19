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
bench.py seed                                    account mode: seed the corpus into the test account (IMAP APPEND,
                                                 pipelined; resumable and idempotent)
bench.py check [--repair]                        account mode: compare the account with the corpus (and repair)
bench.py fetch-parula [--dir tools/parula]       the current public Parula .deb, unpacked without root
bench.py run-linux [--results <folder>]          the whole Linux session (C1 + C2): runs, analysis, results, zips
bench.py corpus     manifest | time | write      deterministic test corpus (profile inbox-30k or multi-folder)
bench.py env        record OS, CPU, RAM, GPU, display, app and server versions, round-trip time
bench.py run        warm-up + 5 measured runs per app and task, interleaved A B A B, with capture
bench.py analyze    --results <folder>: settle detection and checks per run, medians, results.json, evidence.json,
                    report.md
bench.py compose    --results <folder>[,<folder>]: short video (hook, "Go!", race, hold, cards, timeline, subtitles)
bench.py voice      text-to-speech for the lines the composition chose
bench.py method     --results …: method texts below the video (YouTube description, website expander), EN and DE
bench.py encode     WebM VP9 + Opus, MP4 H.264 + AAC, YouTube master (H.264, 2160p), publication gate
bench.py verify     ffprobe checks of the encoded files
bench.py snapshot | calibrate | seed import/verify/wipe   admin mode only (a dedicated instance, see below)
```

A session writes one **result folder** (`results-<os>-<yyyymmdd-hhmm>/`, see "Result folder format") with every
run, the captures and all evidence, plus two zips of it: `…-small.zip` to send (every data file, log and screenshot
of every run, but only the recordings the videos use) and `….zip` with everything; `analyze`, `compose` and
`method` read result folders, so the Linux folder made here and the Windows folder Ben sends are composed the same
way. Both OSes run the same code: one runner (`benchlib/runner.py`), the same flows, probes and analysis; the
Windows session only adds what Windows needs around the runs (`benchlib/winsession.py`). `run` and `run-linux`
continue an interrupted folder with `--results <folder>` (completed runs are kept).

## Account mode (default): an existing server, one test account

The benchmark needs only a host name, an e-mail address and a password (`server.host`, `account.email`,
`BENCH_PASSWORD` or `--password-prompt`). The endpoints follow from the host (JMAP
`https://<host>/.well-known/jmap`, IMAP `<host>:993`, SMTP `<host>:465`; each can be set in the config). Nothing
but that one account is ever read or changed; no SSH, no server administration, no server logs.

- `bench.py seed` (once): appends the corpus over IMAP with many APPENDs in flight on one connection (non-
  synchronizing literals, LITERAL+), the normal user path of every IMAP server; Stalwart's default user limits
  allow it (its JMAP upload quota of 50 MB / 1,000 uploads per hour doesn't). Every pass first reads which corpus
  messages the account already holds (by Message-ID), so an interrupted seeding continues where it stopped and
  never duplicates. It refuses an account that holds other mail (`--delete-foreign` deletes it; the account must
  be a dedicated test account). Tested against a Stalwart with default settings: 30,000 messages (0.5 GB) in 52 s.
- The server needs a valid TLS certificate; a test server's own CA goes into `server.ca_file`.
- Before every run (`start_state.server`), the account check compares every message by its Message-ID, folder
  (Inbox → INBOX, the others by their special-use attribute) and flags with the corpus and repairs differences
  over IMAP: messages moved back, duplicates and messages that aren't from the corpus (e.g. spam that arrived)
  deleted, flags restored (an app that marked a message read), folders an app created deleted, missing messages
  appended. The result is the run's `account.json`; a run whose account still differs after the repair fails.
- `bench.py check [--repair]` runs the same check by hand.

## Windows tests: run once

The Windows tests (C3, C4) are one script that runs everything by itself. **Untested on Windows**: it was written
without a Windows machine (see "What is verified" below).

**The command** (PowerShell, as the normal Windows user, no administrator rights; it asks for the password without
showing it). Until this code is on master, the script comes from the fork's branch:

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/benb-creator/mustang/claude/speed-benchmark-video/benchmark/speed-video/windows/run-windows-tests.ps1 -OutFile run-windows-tests.ps1
powershell -ExecutionPolicy Bypass -File .\run-windows-tests.ps1 -Server mail.example.org -Email test@example.org
```

The script fetches the test scripts of the commit it names as its default `-CodeRef` (repository
`-CodeRepo benb-creator/mustang`), so the script and the code it runs always belong together; the commit is
recorded in `logs\code.json` of the result folder. (From a checkout of the repository: `powershell
-ExecutionPolicy Bypass -File windows\run-windows-tests.ps1 …` uses that checkout; `-Password <pw>` is accepted
too, but then the password is visible in the process list; `-CheckOnly` only checks the prerequisites.) It creates
the folder `parula-speed-test\` where it is started and keeps everything there.

**What it needs:** 64-bit Windows 10 (1809 or later) or 11; Outlook (classic) from Microsoft 365, started and
signed in to Office once; the new Outlook for Windows ("Outlook (new)" from the Microsoft Store) **without
accounts** (or a separate Windows user just for the test); about 60 GB free disk space; the power supply plugged
in; the test account seeded by us (the script checks it and stops if not). Display scaling 100 % is best; other
scalings work when the screen fits a 1280×940 window at that scaling.

**What it does:** fetches pinned tools into `parula-speed-test\tools\` (portable Python 3.13.16, numpy, Pillow,
PyYAML, comtypes, websocket-client, ffmpeg 8.1.2; each file checked by SHA-256) and installs Parula 0.9.39 for the
current user if Parula is missing; checks the prerequisites (apps installed and closed, display, disk, ffmpeg's
`ddagrab`, the account reachable and seeded); asks to close other open apps (waits up to 10 minutes); runs a
**preflight** (each app starts from a fresh state and its instrumentation finds the first page of its account
setup; a 2-second capture test) and stops early with diagnostics if anything fails; then runs the series through
the shared core (`Pipeline.run_session`, the same as `run-linux`): Parula (JMAP), Outlook (classic), new Outlook,
interleaved, 1 warm-up + 5 measured runs each, every run a new account setup, recorded from the screen (ffmpeg
`ddagrab`, lossless, with sync markers), with the account checked (and repaired) before every run and the TCP
connections of each app's processes logged 10 times a second. Runs that fail for a technical reason are recorded
again at the end. Finally it analyzes everything and writes the result folder and its two zips.

**How long:** typically 6–12 hours, depending mostly on new Outlook (its account is kept until its Inbox lists
all messages, at most 2 hours per run, then removed; the next new Outlook run starts at least 10 minutes later).

**Meanwhile:** don't use the computer (no mouse, no keyboard), don't lock it (Windows+L stops the screen
capture), don't open apps, keep it plugged in. Sleep and the screen saver are suspended while it runs. Ctrl+C in
its window stops it and still undoes everything.

**What it changes, and undoes at the end** (also after an error, Ctrl+C or a crash: the next start undoes what a
crashed session left, from `parula-speed-test\state\session-state.json`):
- power plan "High performance" when the computer has it, Windows notifications (toasts) off;
- Parula: a Parula profile of this Windows user (`%APPDATA%\Parula`, `%USERPROFILE%\Parula`) is moved aside and
  moved back; Parula's update check is off (`resources\app-update.yml` renamed back afterwards); the benchmark's
  own Parula profile is deleted after every run;
- Outlook (classic): its own profile `ParulaBench` (`outlook.exe /profile ParulaBench`), deleted after every run
  with the test account's data files and its Credential Manager entries; the user's own profiles and files are
  never touched;
- new Outlook: the test account is added in every run and removed with "Remove from all devices" (also after a
  failed run, when new Outlook lists it);
- the console window is minimized when it covers the recorded area.
Parula stays installed if the script installed it (uninstall in Settings → Apps if wanted).

**The result:** `parula-speed-test\results-windows-<yyyymmdd-hhmm>\` with all recordings, logs and measurements
(layout in "Result folder format") and next to it `results-windows-<yyyymmdd-hhmm>-small.zip` (**the one to send
us**: every measurement, log, check and screenshot of every run, plus the recordings the videos use, i.e. the
median run of each app: 3 of the 18 recordings) and `results-windows-<yyyymmdd-hhmm>.zip` (everything, all
recordings, 10–60 GB; keep it until we confirm). The console and `README-FIRST.txt` in the folder name both zips
with their sizes. The lossless recordings are large where the screen moves a lot: a Parula run with its setup
video is ~200 MB at 1280×940, a run whose screen is still for long stretches much less per minute. On a stop, the folder holds the
diagnostics: `preflight\` (instrumentation dumps and screenshots of every app's first setup page) and
`runs\<app>\T1\<run>\screenshots\`.

**How the flows work:** the same flows and probes as on Linux (`benchlib/flows.py`, `benchlib/probe.py`).
Parula is started with `--remote-debugging-port` and found through its DevTools exactly as on Linux (the same
flow, the same steps, the same video mask; its page texts in English and German); the window system gives the
position of its window's client area. Outlook (classic) and new Outlook are found with UI Automation
(`benchlib/winprobe.py`, element names in `windows/uia-elements.yaml`, English and German; the UI language is
detected from the names that match). Input goes through `SendInput` at the elements' screen positions, like a
user's. Each app's default setup path is taken; the pages that appear decide the next action, and the path is
recorded (`flow_path` in `meta.json`). Every "continue"-type action starts a measured step, which ends at the
last significant screen change before the probe confirms the next page (the last step: the complete Inbox
listing: Outlook's "Items: N" in its status bar, Parula's "N mails", new Outlook's list size or Inbox unread
count; a step after which new Outlook opens its Inbox directly becomes the last step); after the measured end,
the completeness check runs (`verify.json`; in the Outlooks the newest message is selected and End must bring
the corpus's oldest message into view). The instrumentation never gives the time.

**What is verified, what is assumed:** Parula's probe and flow are the Linux ones, tested here against the real
app (0.9.39); its German page texts come from its translations. Outlook's and new Outlook's names are the
visible labels in Microsoft's support articles (`source: docs`) or remembered (`source: assumed`); none was
checked against a real UI Automation tree. The preflight writes those trees, so a wrong name shows up there and
is fixed in `windows/uia-elements.yaml` only. If this Windows user has Thunderbird profiles, Parula's first page
offers to import their accounts (the flow skips it, a measured step; the account names would be visible in the
recording).

## Prerequisites

Linux (C1, C2) — run in this container by us (Ben, round 4), or on any Linux computer:
- An X11 display: `display.xvfb: true` starts a virtual X server (Xvfb, 2560×1440) for unattended runs; with
  `false`, an X11 session (Xorg, not Wayland: ffmpeg `x11grab` and xdotool need X11) with a fixed 2560×1440
  resolution, 100 % scaling, no notifications, screen saver or automatic updates. Two 1280×940 app windows plus
  the bands above and below them fill a 2560×1440 video.
- Python 3.10+ with `pip install -r requirements.txt` (numpy, Pillow, PyYAML, websocket-client, python-xlib).
- ffmpeg ≥ 7 with `x11grab`, `libx264`, `libvpx-vp9`, `libopus`, `drawtext` (freetype), `loudnorm`, `ebur128`;
  the static builds from https://github.com/BtbN/FFmpeg-Builds have all of them. `xdotool`, `taskset`
  (util-linux), `ss` (iproute2), the DejaVu fonts.
- **Parula from the official `.deb`** of the current release (github.com/mustang-im/mustang/releases), unpacked
  without root: `bench.py fetch-parula --dir tools/parula` downloads it and runs `dpkg -x` into
  `tools/parula/root` (or install it with `apt` to `/opt/Parula` and change the config's paths).
  Thunderbird from the official tarball, extracted to `tools/thunderbird/`, with
  `tools/thunderbird/distribution/policies.json` = `{"policies": {"DisableAppUpdate": true}}`.

Windows (C3, C4): `windows/run-windows-tests.ps1` fetches everything it needs, see "Windows tests: run once".
Input goes through `SendInput` (ctypes, `benchlib/windows.py`), the sync marker is a topmost popup window, capture
is ffmpeg `ddagrab` (Desktop Duplication) + `hwdownload`, ffmpeg's CPU affinity is set with
`SetProcessAffinityMask`; the driver is per-monitor DPI aware and checks before every key or typed text that the
app's window is in the foreground, else the run fails and nothing is typed.

## Admin mode (optional): a dedicated Stalwart instance

Only when someone can administer a separate benchmark instance (`server.mode: admin`, the default when the config
has `server.snapshot` or `server.log`): storage snapshots, password rotation and server-log evidence. Run a separate
Stalwart instance only for the benchmark, with its own data directory, so snapshots can stop,
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
`server.log.benchmark_ips`). The evidence: `runs/<app>/<T>/<run>/server-evidence.json` (and `server-log.txt`),
summarized per comparison in `results.json` (`server_evidence`) and the report. The summaries name networks (owner,
ASN, prefix), never single addresses, and never the benchmark computer's address; the raw lines stay in the run
directory.

## Admin mode and calibrated scenarios: setup on the benchmark machine

Only for admin mode (snapshots) and for scenarios with calibrated `steps` (T2–T7, apps without a `flow`). The Linux
T1 runs need none of this.

```sh
cp config.linux.example.yaml config.yaml            # fill in the <…> values
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
and pop-ups. Neither app keeps the password in the desktop keyring. On Windows the session gives every app its
fresh state (see "Windows tests: run once"). Every restore refuses to replace a directory that lacks the
`.bench-profile` marker, so real profiles are never touched.

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

Completion checks of calibrated steps (scenarios with `steps`, e.g. T2–T7):
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

Add `display.masks` or per-scenario `masks` for fixed regions that change on their own (a clock, relative dates);
the report lists every mask, region and setting per app and step. Content that changes by itself and moves with
the app's pages (Parula's setup video) is masked from the probe's report instead (see "Instrumentation").

## Linux tests: run here (C1 + C2), step by step

```sh
cd benchmark/speed-video
cp config.linux.example.yaml config.yaml        # fill in server.host, account.email, the tool and app paths
./bench.py fetch-parula --dir tools/parula      # the current release's .deb, unpacked (dpkg -x), version recorded
export BENCH_PASSWORD='…'                       # or put --password-prompt before the command
./bench.py seed                                 # once: 30,000 messages into the test account (resumable)
./bench.py check                                # optional: the account matches the corpus
./bench.py run-linux                            # the whole session, unattended (hours)
```

`run-linux` starts Xvfb (2560×1440), records the session of `sessions.linux` (Parula JMAP, Parula IMAP,
Thunderbird; 1 warm-up + 5 measured runs each, interleaved A B C A B C, a fresh app profile and the account check
before every run), analyzes every run right after it is recorded, re-records technical failures at the end of the
series, writes `results.json`, `evidence.json`, `report.md` and `README-FIRST.txt` into the result folder and
the two zips next to it (`-small.zip` with the data and the recordings the videos use, and the zip of everything).
It prints the folder, the small zip with its size and the medians (`--no-zip` skips the zip of everything when the
folder is composed on the same machine and disk is short: the lossless captures are most of its size). Interrupted? `./bench.py run-linux --results <folder>`
continues it. On a shared machine, run it under the same lock as other heavy jobs (e.g. `flock <lock file>
./bench.py run-linux`), so nothing else competes for the CPU during the measurement; it runs one app and one Xvfb
at a time.

Then compose from the folder(s):

```sh
./bench.py analyze --comparison C2 --results <folder> [--force]           # again, e.g. after a code change
# set the person-checked facts in <folder>/facts.json (see below)
./bench.py compose --results <folder> --narration <voiceover dir> --variant c2 --lang en --name c2
./bench.py voice --name c2 --lang en                # text-to-speech for exactly the chosen lines
./bench.py compose --results <folder> --narration <voiceover dir> --variant c2 --lang en --name c2   # real lengths
./bench.py method --results <folder> --narration <voiceover dir> --variant c2 --lang en --name c2 --comparisons C2
./bench.py encode --name c2 --lang en
./bench.py verify --name c2 --lang en
```

The same with `--lang de`, and for C1 (`--variant c1`); C1 and C2 come from the same session and the same Parula
JMAP runs. Ben's Windows folder (C3, C4) is composed the same way; the combined cut merges both:
`compose --results <linux folder>,<windows folder> --variant combined` (merging refuses folders whose run counts or
corpus differ; each test shows its own machine).

## Instrumentation (finding the UI, checking completeness)

No calibration: the apps' own debugging interfaces find the elements of each setup page, and the driver clicks and
types there like a user (xdotool on Linux, `SendInput` on Windows).
- Parula (Electron) is started with `--remote-debugging-port`; `benchlib/probe.py` `ParulaProbe` reads its page
  through the Chrome DevTools Protocol (`benchlib/cdp.py`): which setup page is shown, the screen position of
  buttons and fields, the Inbox's message count ("30000 mails"); English and German texts. The same on Windows,
  where the window system tells where its client area is.
- Thunderbird is started with `-marionette -remote-allow-system-access` (and `marionette.port` in user.js);
  `ThunderbirdProbe` reads its Account Hub (shadow DOM), the folder tree and the thread pane's count ("30,000
  Messages") through Marionette (`benchlib/marionette.py`).
- Outlook (classic) and new Outlook (Windows): UI Automation, `benchlib/winprobe.py` `UiaProbe` with the element
  map `windows/uia-elements.yaml` (`probe: {type: uia, app: …, map: …}`).
- The account setup is a flow (`benchlib/flows.py`, `scenarios/T1.yaml` `flow:`): the app's own default path —
  the configuration it finds (autoconfig), or, when the server's domain offers none for that app, its manual setup
  (recorded per run as `flow_path`, and every input of it is a counted user action). Parula 0.9.39 doesn't find JMAP
  by itself (Stalwart's autoconfig lists IMAP, POP3 and SMTP), so Parula's JMAP setup is always its manual setup
  with protocol "JMAP" and the server's URL.
- The instrumentation is never the timing source. Each measured step ends at the last significant screen change in
  the recording before the moment the app's probe confirmed the step's result (the next page, or "the Inbox lists
  all 30,000 messages"); the probe is asked only while the driver's low-resolution live view has been still for
  `quiet_s`, at most once per `probe_interval_s` (one short DevTools or Marionette call), and the live view must
  stay still for another `quiet_s` after the confirmation. A static "Looking up…" or a list that is still loading
  in the background therefore never ends a step early. The message
  count's rectangle (reported by the probe) is a check region of the last step: every change inside it counts,
  however small, so the end is the frame where the count reached its final value, not an earlier, larger change.
- After the measured end the probe checks completeness (`verify.json`): the count equals the corpus, and the
  corpus's oldest message is in the list (Parula: the list scrolled to its end; Thunderbird: the message found by
  its Message-ID and scrolled to). A run that fails it is a differing result (status 3).
- Content that changes by itself: Parula's setup pages play a background video (streamed from www.mustang.im),
  which keeps playing as a user sees it. Ten times a second during the setup (`settle.moving_content_hz`) the
  probe reports where it is visible: the video's rectangle minus the setup dialog (`.page-box`, 12 CSS pixels
  inside its edge for its rounded corners). The driver's live gate leaves that area out at once; every change of
  it is logged (`mask` in `driver.jsonl`, with the poll before that still saw the old one), and the analysis
  applies the same masks to the recording: the old mask stays until the first significant change it sees after
  that earlier poll (the dialog's own layout change, which counts), the new one from the next frame (or 0.1 s after
  the poll that saw it, at the latest). The dialog and everything after the setup count in full. Listed under
  deviations; `analysis.json` `moving_masks` records the masks and when each applied.
- Disclosed in the manifest (`instrumentation`) and the report. Benchmark-only inputs (e.g. closing a first-run
  notice an app shows in between) are logged as `prepare` and not counted.

## Network evidence (client side)

Every run of every app logs the TCP connections of the app's process tree ten times a second (`network.jsonl`;
Linux: `/proc`, byte counters from `ss -tni`), together with the mail server's addresses as this computer resolves
them at the start of the run. `analyze` summarizes each run (`evidence.json`: connections to the mail server on
its mail ports, bytes received over them, connections on mail ports to other addresses, every other remote network
by owner, ASN and prefix from RDAP and RIPEstat, cached) and each comparison (`env.<C>.left_direct_only`,
`right_direct_only`; for an app with `cloud_sync: true` also `right_direct_connections`, `right_inbox_complete`,
`right_remote_owner`, `right_remote_asn`). `direct_only` = the app connected to the mail server in every measured run
and to no other address on a mail port with more than a probe's few bytes (an app that guesses host names
probes other addresses; that isn't mail data) and to no proxy. Raw addresses stay in `network.jsonl`; the
summaries publish networks, never single addresses, and never this computer's public address.

## Result folder format

```
results-<os>-<yyyymmdd-hhmm>/                 os = linux | windows
  manifest.json      format "parula-speed-results", version 1, tool (git commit, dirty), config (secrets removed,
                     the account address reduced to its domain), server (mode, host, endpoints), corpus (profile,
                     counts, oldest/newest subject, digest), environment per session, apps, deviations, procedures,
                     instrumentation, sessions, comparisons, run plan (order, app, run, warm-up) and run counts
  facts.json         person-set facts (template; never filled in by the pipeline)
  runs/<app>/<task>/<run>/     run = warmup-1, run-1 … run-5; run-N.failed-K = a failed attempt recorded again
    meta.json        status (complete | timeout | failed + reason), app version, order, attempt, setup path,
                     user actions (count and list), benchmark-only inputs, inbox_complete, timestamps
    driver.jsonl     every input, marker, step start, live-gate result and probe answer (monotonic clock)
    capture.mkv      the lossless capture (app area + sync-marker strip), capture.json how it was made
    changes.npz      per-frame change measures (analysis), analysis.json the run's analysis (steps, durations,
                     clock fit, first rows visible, tail, measured window, wall-clock elapsed)
    network.jsonl    connections of the app's processes, evidence.json their summary
    verify.json      the completeness check after the measured end
    account.json     the account check and repair before the run
    screenshots/     on a failed run: the screen and the app's UI state
    app-output.log, ffmpeg.log, error.txt (secrets redacted)
  preflight/         Windows: the preflight's result, screenshots and UI dumps of every app's first setup page
  results.json       per comparison and task: left/right medians, min, max, status, runs in run order, actions,
                     setup path, first rows visible, wall-clock elapsed, evidence summary, environment, corpus
  evidence.json      the evidence facts per comparison (the narration's env.<C>.* values)
  report.md          the human-readable report
  logs/              session logs (secrets redacted)
  README-FIRST.txt   for the person who ran it: where the folder and the zips are, how big, what to send
results-<os>-<yyyymmdd-hhmm>-small.zip      every file except the recordings the videos don't use (to send)
results-<os>-<yyyymmdd-hhmm>.zip            everything (recordings stored, not recompressed)
```
All JSON is self-describing (keys named as above; times in seconds; UTC as ISO 8601 or epoch seconds where noted).
The password never appears in any file: typed text that is a secret is logged as `<secret>`, error texts are
redacted, and the config holds only the name of the environment variable.

### Facts set by a person (`<result folder>/facts.json`)

`analyze` creates the template; the pipeline never fills it. Per comparison:
`right_protocol_default: 1` after checking our own T1 recording that the right-hand app's own account setup chose
IMAP for this server; for C4 also `cloud_sync_confirmed: 1` (new Outlook's setup screen in our recording says the
account syncs through the Microsoft cloud), `dialog_text` (that screen's text, typed from the recording) and
`microsoft_footage: 1` once a lawyer confirmed Microsoft's screenshot permission covers the C4 footage.
The server-log facts (`left_direct_only`, `cloud_login_confirmed`, `cloud_fetched_messages`, …) come from the
evidence.

### New Outlook (C4)

New Outlook syncs IMAP accounts through the Microsoft cloud, so its state can't be restored from a snapshot.
Every C4 run of new Outlook is a new account setup. In account mode (the Windows script): after the measured end
the account stays in new Outlook until its Inbox has listed all messages for 3 minutes (at most 2 hours; not
measured time), then it is removed with "Remove from all devices" (also from the Microsoft cloud; Microsoft names
it as the way to delete the stored credentials), and the next new Outlook run starts at least 10 minutes later
(`benchlib/winsession.py` `NewOutlookLifecycle`). If the removal fails, the series stops, because the next run
would not be a new setup. The evidence is client-side ("Network evidence"): whether any of new Outlook's
processes connected to the mail server at all, and whether its Inbox listed every message anyway.

In admin mode (a server log is available), the scenario's `finish` sequence can instead wait until the server log
shows no fetch and then no login from outside the benchmark computer (`wait_cloud_quiet`), and the server-log
evidence (`cloud_logins_after_removal`, `cloud_fetched_messages`, `cloud_fetched_headers`, after the last run
`server.log.final_watch_min`) is recorded. The procedure is listed in the report and the method text.

Every variant may only be published when its `publish_when` in `compose.json` holds (C4:
`cloud_sync_confirmed`, `cloud_login_confirmed`, `left_direct_only`; the combined cut also one session per
computer). `encode` refuses otherwise and names the first variant of its `publish_instead` chain whose own
condition holds (e.g. `c4-direct`), or none; `encode --internal-preview` makes a copy marked "not for publication"
for review. In variants with the data-path card, new Outlook's pane shows footage only when
`c4_microsoft_footage_when` holds (`microsoft_footage` in `facts.json`), otherwise a neutral timer card.

## What a run does

Check and repair the test account (account mode) or restore the server snapshot (admin mode); reset the app's
profile (fresh for T1); start the network log; start the app and attach its probe; bring it to the task's start
state (live-only capture, not recorded); start the recording; show 5 sync markers;
for each step do its actions — the timer starts at the step's last input event; after a click the pointer moves
out of the recorded area — and wait until the live low-resolution stream has been still for `quiet_s` (the same
quiet period the analysis uses) and matches the step's references; run the step's verify actions; show 5 sync
markers; record the scenario's tail (T1: 30 s, to show what the app does after the list is complete); show 5
markers; stop the recording; run the finishing sequence (new Outlook: keep, then remove the account); close the
app; reset what it left (Windows: its profile); stop the network log (admin mode: collect the server log of the
run). A series that can't go on (a required finishing sequence failed, or less than `runs.min_free_gb` is free for
the next recording) stops; the runs so far are analyzed and packaged. A flow decides its steps while it runs (the page the app shows); the analysis reads
them back from `driver.jsonl`.

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
  regions (and, while it is shown, content that changes by itself, see "Instrumentation") are ignored, except
  inside the step's check regions, where every change counts; slow fades are found
  by comparing with the frame 6 frames earlier. A step ends at the last significant change before at least
  `quiet_s` without one, at a frame that matches the step's references and regions — or, for a flow step, in the
  quiet period during which the app's probe confirmed the step's result (see "Instrumentation"). Duration = time of that frame
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

- Same computer, OS install, display resolution, window size, network, server and test account. Default
  settings of each app; every deviation goes into `deviations` in the config and from there into the report and
  the method text; procedures (e.g. the account removal in new Outlook) into `procedures`.
- Apps are recorded one after another, never at the same time, interleaved A B A B; the video shows them side by
  side, synchronized at the start of each task, and says so in its footnote. If the panes would finish on screen
  in another order than their timers stop (typing between the setup steps), each pane shows only its waiting
  periods back to back and the footnote says "typing cut out".
- Before each run the test account is checked against the corpus and repaired (account mode) or the server
  snapshot is restored (admin mode), and the app starts from a fresh profile. One warm-up run per app and task is
  discarded (disclosed).
- Both apps get the same instrumentation treatment: their probes are asked only while the screen is still, about
  once per second, and the same typing speed and click timing (xdotool with no extra delay) apply to every app.
  An app's own moving content is not paused or switched off: it plays as for every user, and only its area is
  left out of the change detection (disclosed). Then 5 measured runs; the median is reported with min and max; the video shows
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
                                                           # gaps and the completion gate; clock fit; censored
                                                           # medians and statuses; snapshot guards; server-log
                                                           # parsing; account check and repair; network log
                                                           # parsing and evidence; result folder; live gate with
                                                           # a probe; setup flows with a fake app probe;
                                                           # masks over moving content (live and offline);
                                                           # result folder zips;
                                                           # narration, spoken durations, method templates,
                                                           # speech; corpus profiles and determinism
BENCH_VOICEOVER=<voice-over dir> python -m pytest tests/   # also every real variant and method template
BENCH_PWSH=<pwsh> BENCH_PSSA=<PSScriptAnalyzer module dir> python -m pytest tests/test_windows.py
                                                           # Windows logic with fakes (UI Automation probe and
                                                           # the Outlook flows through the shared driver,
                                                           # lifecycles, session cleanup), plus the PowerShell script
                                                           # parsed and checked for Windows PowerShell 5.1
tests/e2e_fake.py --work /tmp/e2e --tools <dir with ffmpeg, Xvfb, xdotool>
tests/snapshot_check.py --config config.yaml [--protocol-level]       # admin mode only
```

The real apps are tested end to end against a local Stalwart instance in account mode with a smaller corpus
(3,000 messages): `seed`, `run-linux --runs 2 --warmup 1`, `compose --results <folder>`. A local test server's own
CA goes into `server.ca_file` (the probes make Thunderbird trust it; Parula needs `NODE_EXTRA_CA_CERTS` in its
`env`), and its non-standard ports into `server.imap` / `server.smtp` / `server.jmap_session_url`.
