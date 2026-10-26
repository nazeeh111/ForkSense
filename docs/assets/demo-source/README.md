# Genuine report walkthrough

`../demo.mp4` is a silent, 24-second recording of interaction with the sanitized report from the measured live Codex run. It is **not a real-time recording of the agent working**. The underlying run took 63.70455 seconds, used one diagnostic probe and one repair call, and the selected patch passed four independently supplied contract tests. This single demonstration is not a benchmark comparison.

The desktop and mobile screenshots show that same report at widths of 1440 and 390 pixels. The report renderer includes the later source-patch inspection control and accurate worktree-fork map; this changes presentation of the existing run evidence and does not imply the agent was rerun. The original failed probe, source patch, test output, and reported totals are preserved.

The capture uses installed Playwright and Chrome's native screencast. Chrome emits frames when the viewport changes. Original frame timestamps determine the intervals; FFmpeg holds each observed frame until the next timestamp. The final output samples that sequence at 25 fps and trims the last hold at 24 seconds. There are no invented agent events, edited measurements, accelerated agent footage, synthetic motion frames, external assets, or audio.

The visible sequence is the actual report: run totals, frozen-base worktree forks, the failed tax probe, independent verifier output, exact source patch, and selected patch identity. The probe and repair are sibling forks from the same base; the verifier is a fresh worktree containing the base plus candidate patch. The chronological evidence remains a separate view. Fixed captions identify the clip as a report walkthrough. Raw native frames, unsuccessful capture attempts, and the previous valid report HTML are retained in the ignored task-local `.local-evidence/media-v1` and `.local-evidence/media-fork-map-v2` folders. The public manifests retain source and media SHA-256 hashes.

## Reproduce with installed tools

From the repository root, with Playwright available to Node and an installed Chrome/Chromium:

```sh
node scripts/demo_capture.cjs /tmp/forksense-capture-new
python3 scripts/demo_encode.py /tmp/forksense-capture-new /tmp/forksense-encode-new
```

Both scripts require fresh output directories and preserve earlier renders. `FORKSENSE_CHROME` can select an existing browser executable; `NODE_PATH` can select an existing Playwright installation. No browser, package, or runtime download is performed. The capture defaults to the committed sanitized report and the transcode uses installed FFmpeg and ffprobe.

`map-verification.json` records the current-source desktop/mobile map and keyboard-navigation checks. `capture-manifest.json` identifies exact HTML, JSON and patch sources, native frame hashes/timestamps, and actions. `media-manifest.json` records the transcode, trim, hashes and format checks. `ffprobe.json` and `full-decode.log` establish dimensions, duration and successful full decoding. `playback-verification.json` records a normal-speed browser playback check. Representative encoded frames, including the assertion failure, all four passing tests and complete patch, were visually inspected.
