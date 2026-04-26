# Plug and Play

Tamper-proof self-capture for insurance underwriting. Replaces forgeable screenshots and \$300 in-person inspections with AI-verified live captures whose anti-cheat layers are the actual product.

Built at the Plug and Play hackathon (Sunnyvale, CA).

---

## What it does

Three customer-facing features, each replacing a load-bearing piece of traditional underwriting with a self-capture flow that's hard to fake:

### 1. Live Phone-Screen Video Capture — `web/`

Personal-line risk signals (Uber driver rating, Duolingo streak, Spotify Wrapped, Oura sleep score, Apple Health steps) sourced from a short live video the user records on their laptop while pointing their phone at the webcam. The screenshot doesn't exist, so it can't be Photoshopped.

Anti-cheat stack:

- **File integrity** — SHA-256 of the upload, recomputed server-side
- **Splice / continuity** — perceptual-hash distance between consecutive sampled frames; jumps above threshold flag a hard cut
- **Light vs. solar elevation** — frame luminance cross-checked against the sun's elevation at the GPS coords + timestamp ("claimed midday outdoors but pitch dark" trips this)
- **Spoken challenge code** — server generates a random 4-character code after the request starts; user reads it aloud during recording; `faster-whisper` (tiny.en, local) transcribes the audio track and a subsequence match verifies the code appears in order. Whisper-mangling tolerance built in (e.g. "Quebec" → "quib-back" still passes).
- **Physical phone in frame** — Claude Vision determines whether a real phone with bezel/hand/reflection is visible vs. a screen-of-a-screen recording

Score extraction: keyframes go to Claude Sonnet 4.6 with a structured-output JSON schema; returns the platform, signal type, value, confidence, and a one-line extraction note.

### 2. Verified Space Scan — `ios/`

Replaces the in-person commercial-property hazard inspection. Owner walks through their space holding an iPhone Pro; the app captures a continuous LiDAR-equipped scan with concurrent front-camera face tracking.

Anti-cheat stack:

- **Operator face visible (front cam)** — `ARWorldTrackingConfiguration.userFaceTrackingEnabled = true` provides face anchors from the front camera while the back camera + LiDAR are doing the scan. A scan with no front-camera face for most of its duration looks like a propped phone or a video replay.
- **LiDAR coverage** — minimum mesh-triangle and anchor-count thresholds; tiny corner-of-a-room captures are rejected.

Hazard analysis: ≤60 keyframes (server subsamples and resizes to keep request size sane) plus a mesh summary go to Claude Sonnet 4.6 with a structured schema. The model returns:

- Fire extinguishers and exit signs as `{frame_index, bbox, confidence}` arrays so we know *where in which frame* the model saw each item
- Slip/trip hazards with `{frame_index, bbox, description, severity}`
- Exits-unobstructed boolean, clutter score (0-1), lighting-adequacy enum, estimated floor area, prose summary

Server then renders bounding boxes onto copies of the source keyframes (green for safety equipment, red/orange/amber by severity for hazards) and returns URLs to the annotated images. The iOS result sheet shows a horizontal carousel of these annotated frames so you can audit *exactly* what the model identified and where.

### 3. Peer Recommendations & Vouching

Trust-graph layer over the policy-issuance flow. Users can request recommendations from other users, and each vouch contributes a reputation-weighted boost to the recipient's underwriting profile. The recommender's own platform reputation determines the strength of the boost — established users with consistent vouching history move the needle more than new accounts.

Implementation lives in a separate repository — *(link TBD; ask the maintainer)*. The trust-graph service exposes a vouching API that the underwriting scorer consumes when present, and degrades cleanly to the Feature 1 + 2 score when absent.

---

## Architecture

```
┌────────────────────┐         ┌──────────────────────────┐
│ Laptop browser     │  HTTPS  │  FastAPI backend         │
│ web/index.html     ├────────►│  /verify/phone           │
│ (Feature 1)        │         │  /verify/space           │
└────────────────────┘         │  • anti-cheat checks     │        ┌──────────────────┐
                               │  • Claude Vision (cached │───────►│ Anthropic API    │
┌────────────────────┐         │    prompts + structured  │        │ Sonnet 4.6       │
│ iPhone Pro app     │  HTTPS  │    JSON schemas)         │        └──────────────────┘
│ ios/PlugAndPlay    ├────────►│  • OpenCV bbox annotator │
│ (Feature 2)        │         │  • Whisper audio xscript │
└────────────────────┘         └──────────────────────────┘
```

Backend serves the web app at `/`, persisted uploads at `/uploads/<scan_id>/...`. API key (Anthropic) lives in `backend/.env`, never in the iOS binary or web client.

## Stack

| Surface | Tech |
|---|---|
| Web (Feature 1) | Single-file `web/index.html`, vanilla JS, `getUserMedia`/`MediaRecorder`, `crypto.subtle` for SHA-256, `fetch` for multipart upload |
| iOS (Feature 2) | SwiftUI + ARKit, `ARWorldTrackingConfiguration` with mesh + concurrent face tracking, async/await, XcodeGen for project spec |
| Backend | Python 3.12, FastAPI + uvicorn, OpenCV (`opencv-python-headless`), `imageio-ffmpeg`, `faster-whisper` (tiny.en), Anthropic SDK |
| AI | Claude Sonnet 4.6 (vision + structured outputs + prompt caching). Anti-cheat verification is fully deterministic Python; only signal extraction and hazard reporting hit the model. |
| Trust graph (Feature 3) | Separate service / repo — see above |

## Quickstart

Backend:

```sh
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # add your ANTHROPIC_API_KEY
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
```

Web (Feature 1) — visit:

```
http://localhost:8000/
```

iOS (Feature 2):

```sh
brew install xcodegen
cd ios && xcodegen
open PlugAndPlay.xcodeproj
```

In Xcode: pick a development team, plug in an iPhone Pro (LiDAR required), Cmd+R. In the app's Settings tab, set Base URL to your laptop's LAN IP (`http://<laptop-ip>:8000`) — or run a public tunnel (`brew install cloudflared && cloudflared tunnel --url http://localhost:8000`) if you're on a venue network with AP isolation or DNS filtering.

Demo Mode: there's a toggle in the iOS Settings tab that returns canned fixture responses without hitting the backend — for offline judging when conference Wi-Fi misbehaves.

## Repo layout

```
plug_and_play/
├── web/                      # Feature 1 — laptop webcam recorder
│   └── index.html
├── ios/                      # Feature 2 — iPhone Pro space scan
│   ├── project.yml           # XcodeGen spec (regenerate the .xcodeproj from this)
│   └── PlugAndPlay/
│       ├── App/              # SwiftUI app entry
│       ├── Features/
│       │   ├── SpaceScan/    # ARSpaceScanner + view model
│       │   └── Settings/     # backend URL, demo mode
│       ├── Models/           # Codable result types
│       └── Services/         # BackendClient, LocationService, VideoHasher
└── backend/                  # FastAPI + Anthropic
    ├── app/
    │   ├── routes/           # /verify/phone, /verify/space
    │   ├── anticheat/        # hash, splice, light, audio, face_continuity, mesh_coverage
    │   ├── vision/           # Claude Vision wrappers (phone signal, space hazard)
    │   ├── services/         # video frame extract, audio transcribe, bbox annotation
    │   └── scoring/          # underwriting score
    ├── pyproject.toml
    └── .env.example
```

## What's deliberately not here

The first cut of the plan included a few harder-to-demo pieces; we cut them so the core anti-cheat story would actually ship in a hackathon timeframe:

- Per-frame rolling SHA-256 bound to the camera capture pipeline (the file-level hash we ship catches post-upload tampering only — see `backend/app/anticheat/hash_verify.py`)
- Random post-policy re-verification triggers
- Audio-fingerprint reverse-lookup against GPS-implied environment
- LiDAR-mesh diff against prior scan (catches staged cleanups)

Those are documented in the original plan and would be the next obvious work if this were going to production.
