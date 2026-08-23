# The model registry

One file per model in `models/`. One entry per thing you can actually download.
Everything else — the CLI, the MCP server, the onboarding page, the
compatibility engine — reads from here. Adding a model means adding a file.

## Why numbers carry a source

Every figure in this registry states where it came from, and the loader refuses
a bare number. Not bureaucracy — the whole reason for this project.

Nine sites will tell you a model's "VRAM requirement". None of them tells you
whether that figure was measured on hardware, summed from a file listing, or
derived from a rule of thumb. They read identically, so a reader cannot weigh
them, and an estimate that has been repeated often enough starts to look like a
fact. The one real Apple Silicon video number we could find anywhere — 82
minutes for a two-second clip on an M1 Max — was on a personal blog, absent
from every database that claims to answer this question.

So: `measured` means somebody ran it and wrote down what happened.
`huggingface-api` means it was summed from the Hub's file metadata on a stated
date. `declared` means a source outside this project published it, and the note
says which. `estimated` means we derived it, and the note must say from what.

An estimate without its derivation will not load. A measurement without a date
will not load.

## Why variants

A model is not a download. `Lightricks/LTX-Video` holds every checkpoint the
project has ever shipped — 236 GB in total, when the one file you want is 5.9 GB.
A variant names its `files`, and the download narrows to them. Where two
variants share a repo, naming files is enforced by a test.

## Fields

```yaml
schema: 1                 # refuses to load under a different reader
id: ltx-video             # stable; other things reference it
name: LTX Video
family: lightricks
kind: video               # video image audio speech text vision
summary: one line
homepage: url

license:
  id: LTX Community
  spdx: null              # null when it is not an SPDX licence
  open_source: false
  url: ...
  restrictions:           # required when open_source is false
    - Free only while your annual revenue is under $10M

variants:
  - id: ltx-video-2b-098-distilled
    name: LTX Video 2B 0.9.8 distilled
    params: 2B
    precision: bf16
    repo: Lightricks/LTX-Video
    files: ["ltxv-2b-0.9.8-distilled.safetensors"]   # omit to take the whole repo
    backends: [metal, cuda]     # metal cuda rocm cpu
    download:
      value: 6350000000
      source: huggingface-api
      checked: "2026-08-22"
    working_set:                # peak while generating, not file size
      value: 10200547430
      source: estimated
      note: says exactly how this was derived
    speed:                      # empty until somebody measures it
      - device: Apple M1 Max 32GB
        backend: metal
        metric: seconds_per_second_of_video
        value: 2460
        source: measured
        measured_on: "2026-08-22"
        note: resolution, frame count, anything needed to reproduce it
```

`speed` metrics: `tokens_per_second`, `seconds_per_image`,
`seconds_per_second_of_video`, `realtime_factor`, `load_seconds`.

## Keeping it true

```bash
python tools/verify_registry.py          # re-resolve every repo against the Hub
python tools/verify_registry.py --fix    # rewrite drifted sizes, restamp dates
```

Run it before publishing anything derived from this registry. It exits non-zero
on drift, so it can gate a release. It also names every variant that still has
no measured footprint or speed on any machine — which today is most of them, and
saying so is the point.
