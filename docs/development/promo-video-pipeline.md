# Promo Video Pipeline — ComfyUI

Working notes for generating short promotional films for Heart of Virtue in the
style of 1990s animated series (Batman: TAS / X-Men "dark deco").

**Status:** first film in progress — the Mara chronicle, six beats, 15.25s.
**Last updated:** 2026-08-25

This is a living document. Findings here were paid for with failed renders.

## If you read nothing else

1. **The keyframe is the film.** The clip inherits its palette, line quality and
   costume almost completely. Spend effort there, not on the video prompt.
2. **Write the video prompt as small bounded events**, and explicitly negate the
   dramatic version of each. "Stones skitter down" became a second rockfall.
3. **Never use a three-quarter pose for a character** you need to survive the clip.
   Fully turned away or fully front-on. See "Characters in I2V".
4. **Assert stillness as forcefully as action.** A model trained on video assumes
   people do things.
5. **Batch 5+ seeds and pick.** Flying objects and melted faces are seed luck, not
   prompt faults. Rewriting the prompt to fix them is chasing ghosts.
6. **Look at the frames.** The motion index detects *frozen* and nothing else — it
   has misled me six separate times in one session.

---

## Environment

The ComfyUI install is **split across two directories**, and this has caused three
separate failures so far. It is the first thing to check when something is
mysteriously invisible.

| What | Where |
|---|---|
| App / server | `dev\cui-video\Video\ComfyUI\` (port 8188) |
| Workflows | `dev\cui-video\Video\ComfyUI\user\default\workflows\` — beside the app |
| **input** | `dev\ComfyUI\input\` — **redirected** |
| **output** | `dev\ComfyUI\output\` — **redirected** |
| Models | `C:\Users\azure\ComfyUI-Shared\models\` — shared, survives updates |
| Custom nodes | `dev\cui-video\Video\ComfyUI\custom_nodes\` — **only** this one is scanned |

Two consequences:

- Copying a keyframe into the `input` folder sitting next to the app does nothing.
  `LoadImage` will reject it as "Invalid image file".
- Custom nodes installed in `dev\ComfyUI\custom_nodes\` are invisible to the running
  server. IPAdapter was already installed there and had to be re-cloned.

**Don't trust the filesystem — ask the server.** `GET /object_info/LoadImage` returns
the exact list of images the node will offer. `GET /models/<type>` lists what it can
actually see. Model directories are re-scanned per request; **custom nodes are only
registered at process start**, so a new node needs a full restart.

### Hardware ceiling

RTX 2070, 8 GB VRAM, 16 GB system RAM. This rules out most current video models.

---

## Model stack

### Why not MiniMax H3

The first attempt used the bundled `video_minimax_h3_t2v` template. Abandoned:

- 42.4 GB of weights (20 GB diffusion + 15 GB text encoder + 5.5 GB VAE)
- Peak working set ~25 GB against 16 GB RAM — disk paging, not slowness
- Its text encoder is `nvfp4_awq`, a **Blackwell** format. On Turing there is no
  hardware FP4, so it dequantises in software

Deleted, freeing 41.4 GB.

### What we use

| Role | Model | Size |
|---|---|---|
| Video | `wan2.2_ti2v_5B_fp16` | 9.31 GiB |
| Video text encoder | `umt5_xxl_fp8_e4m3fn_scaled` | 6.27 GiB |
| Video VAE | `wan2.2_vae` | 1.31 GiB |
| Stills | `sd_xl_base_1.0` | 6.5 GB |
| Identity | `ip-adapter-plus_sdxl_vit-h` | 809 MB |
| Identity encoder | `CLIP-ViT-H-14-laion2B-s32B-b79K` | 2.35 GiB |

Total working set for video is ~11.4 GB, because the text encoder runs once and is
evicted before sampling. That is what makes it fit where H3 didn't.

WAN generates **no audio**. Score separately with the ACE-Step workflows.

---

## The pipeline

```
SDXL + IPAdapter  ->  keyframe (1024x576)
                          |
                          v
      WAN 2.2 TI2V-5B  (start_image)  ->  clip (~2-3s)
                          |
                          v
              assemble six clips in an editor
                          |
                          v
                  score with ACE-Step
```

One beat per clip. Cutting between shots is not a workaround — it is how the
coherence window is handled, and it is how film has always worked.

### Timing (measured, not estimated)

- **Video: ~2 minutes per clip** at 1024×576 / 61 frames, after the model is loaded.
  Both a proving run and the real render finished in 355s *including* a cold 10 GB
  load. 1024×576 does not strain the 2070.
- **Stills: ~55s per batch of 2** at 1344×768.

Video is cheap. Keyframes are the bottleneck, and they are also what determines the
result — see below.

### Frame counts

WAN 2.2's VAE compresses 4× in time, so valid lengths are **4n+1**: 49, 53, 57, 61,
65, 69, 73. Divide by 24 for seconds. Asking for 60 will not do what you meant.

---

## Hard-won findings

### The keyframe *is* the film

The clip inherits the keyframe's palette, costume, hair colour and line style almost
completely. A video prompt asking for a burnt-orange sky rendered the keyframe's pale
teal instead. Identity held across all 61 frames with no morphing.

**Consequence:** keyframe quality is the highest-leverage thing in the pipeline. Do not
treat stills as a preliminary. Directing the video prompt against the keyframe's own
content is a losing fight.

### Keyframe detail × resolution is what freezes clips (not resolution alone)

⚠️ **This section previously recommended rendering at native resolution. That was wrong
and is retracted.** The reasoning is preserved here because the mistake is instructive.

Beat 01 was rendered from the same keyframe at 1024×576 and 1280×704. Comparing frame 46
of each, the 1024 clip was smeared and melted while the 1280 clip looked pristine — so
native resolution appeared to preserve detail dramatically better.

It looked pristine because **it was still the input image.** At 1280×704 every one of the
49 frames came back byte-identical: mean frame delta 0.00, max frame delta 0. The clip
was the keyframe copied 49 times. I had compared a degrading video against a still frame
and credited the still frame with superior fidelity.

The ComfyUI log shows the mechanism:

```
[WARNING] Ran out of memory when regular VAE decoding, retrying with tiled VAE decoding.
```

1280×704 × 49 frames exceeds 8 GB. Note that the job still reports **success** — there is
no error, no failed status, and the output file is valid H.264 of the correct dimensions
and frame count. Only the pixels are wrong.

**Always measure motion on a new resolution or length.** A silent freeze is
indistinguishable from success by every signal except the frames themselves.

**The real variable is the keyframe, not the resolution.** Measured after a VRAM flush,
both at 1024×576:

| Keyframe | Motion index |
|---|---|
| SDXL (coarse, 1344×768 source) | **56.37** — reproduces reliably |
| Nano Banana 2 (crisp, 1376×768 source) | **12.36** |

The *same* NB2 keyframe scores **61.34 at 704×384**. So it is not the image alone and not
the resolution alone — it is the interaction. At 704 the downscale destroys enough
structure that the model has latitude; at 1024 it preserves enough to lock onto and
simply reproduce.

Two probable contributors: the crispness gives WAN a confident structure to anchor to,
and the composition is a **static tableau** (two motionless figures) where beat 06's
keyframe is someone mid-stride, which implies where the next frame goes.

**Attempted fixes that did not work** (NB2 keyframe, 1024×576, 49f):

| Intervention | Motion index |
|---|---|
| baseline, shift 8.0 | 12.36 |
| shift 5.0 | 0.00 |
| shift 3.0 | 0.00 |
| shift 8.0 + 2px blur on start_image | 7.30 |

Lowering `shift` made it *worse* and froze it outright — despite shift 5.0 scoring
*higher* than 8.0 at 704×384. That inconsistency, plus the spread across NB2-at-1024
runs (0.00, 0.00, 4.26, 7.30, 12.36), suggests instability rather than a clean parameter
response. Treat single runs here as unreliable evidence.

**Known-good combinations:**

| Keyframe | Resolution | Frames | Motion |
|---|---|---|---|
| SDXL | 1024 × 576 | 61 | 52–56 ✅ |
| NB2 | 704 × 384 | 49 | 61 ✅ |
| NB2 | 1024 × 576 | 49 | 0–12 ❌ |
| any | 1152 × 640+ | 49 | 0.00 ❌ |

### Degradation is progressive — trim in the edit

Even at native resolution, quality decays across a clip. Frames 0–20 hold, and the last
third softens. Render the full length and **cut early in the edit** rather than trying to
render exactly the length you need.

### Motion comes from verbs, and only from verbs

Measured with a proper control — same resolution, same seed, only the prompt differing:

| Prompt @ 704×384, seed 10101 | Motion index |
|---|---|
| Static description (contained "The girl does not move") | 38.45 |
| Every moving element given its own verb | **61.34** |

Giving the lamp flame *flickers and gutters*, shadows *slide and sway*, canvas
*breathes*, blanket edge *lifts and settles*, hair *stirs*, girl *blinks* — worth about
**+60%**.

⚠️ An earlier version of this note claimed 0.00 → 61.34. That was wrong: the 0.00 came
from a clip frozen by an unrelated resolution fault, compared against a working clip at
a different resolution. Two variables, one conclusion. Always run the control.

**Write the video prompt as a list of events, not a description of a frame.** The
keyframe already establishes what the scene looks like; the prompt's job is to say what
happens in it. This is the single most common way to waste a render.

**But WAN escalates whatever you name.** The opposite failure is just as easy. Beat 02's
prompt said *"a few small stones come loose high on the slope and skitter down"* — WAN
rendered a second full rockfall, boulder in mid-air, dust swallowing half the frame by
the end of the clip. A model trained on video has a strong prior toward things
*happening*.

So the rule is narrower than "add verbs":

- Name movements that are **small, bounded and continuous** — a mule shifting its weight,
  a corner of cloth lifting and settling, hair pulled sideways.
- **Explicitly negate the dramatic version** of whatever you just described. "The rockfall
  is already over and nothing more falls: the slope is still, no boulders move." A
  rockfall scene invites a rockfall; not asking for one is not enough.
- **Prefer verbs that reveal over verbs that obscure.** "Dust still hangs in the air"
  produced a thickening cloud that washed out the frame; "dust thinning and settling,
  drifting away and slowly clearing to reveal the rubble behind it" gave the same
  quantity of motion while opening the shot up instead of closing it down.
- Stillness sometimes needs stating too. "She does not move otherwise, does not turn
  around, and does not react" — otherwise the model gives her a reaction shot, which is
  usually a more conventional character than the one in the lore.

Ambient life — flame, fabric, hair, breath, a slow push-in — is usually enough. A held
shot does not need someone to cross the frame.

### Characters in I2V: three-quarter poses are the fragile case

**The keyframe's pose decides whether a character survives the clip.** WAN can only
animate geometry the keyframe gave it.

| Pose in keyframe | Result |
|---|---|
| Fully turned away | Safe — no face to lose |
| Fully front-on | Safe — the face is completely specified |
| **Three-quarter / partly turned** | **Fragile** — any rotation forces the model to invent the unseen side, and a 5B model invents it badly |

Beat 02's keyframe had Mara back-three-quarters on. WAN rotated her slightly and her
face came apart during the turn. This is **systematic, not seed luck** — there is no
information in the keyframe to preserve, so no seed will save it.

Plan for this at the storyboard stage. It costs nothing to compose a shot with the
character fully turned away, and it removes an entire class of failure.

### Stillness must be asserted, not implied

"She does not move otherwise, does not turn around" was not enough — WAN turned her
anyway. A model trained on video has a strong prior that people in shots *do things*,
and a single negative clause does not overcome it.

What worked was stating it six ways and backing it with negatives:

> She stands completely motionless with her back to the camera. She is frozen in place
> like a figure in a photograph. She does not turn. She does not turn her head. She does
> not look around, does not move her arms, does not shift her feet, and does not walk.
> Her face is never shown.

plus `person turning, turning head, looking over shoulder, face visible, character
rotating, figure walking` in the negative.

A "living still" — parallax and ambient motion around a frozen figure — is a legitimate
and very common montage technique. It is also by far the most reliable thing this
pipeline produces.

### Things fly into the frame

WAN invents objects entering from implied off-screen space. One beat 02 seed produced a
**second mule flying through the air** in the upper left, gone again twenty frames later.

This is **stochastic**. It is not fixed by prompt work — it is dodged by generating
several seeds and discarding the bad ones. Add `entering frame, flying object, floating
animal, extra animal, duplicate <subject>, object falling from sky` to the negative as
cheap insurance, but the real defence is candidates.

### Batch seeds for stochastic faults; rewrite prompts only for systematic ones

Tell them apart before spending a render:

- **Systematic** (every seed, traceable to the prompt or keyframe): a frozen clip, a
  missing prop, a face degrading on rotation, a second rockfall. Fix the input.
- **Stochastic** (one seed in five): flying objects, a transient melt, a duplicated
  limb. Generate more seeds.

Rewriting a prompt to fix a stochastic fault changes several variables at once and
teaches you nothing — and it is how beat 01 flip-flopped through four passes.

### Screening clips: sample at least four frames, and watch the peak

Report **mean and peak** frame delta. A peak far above the mean means something appeared
or jumped in a single frame — the flying-mule signature. That is a job the index is
actually suited to: flagging which clips to open first.

Sample four or more frames per clip when screening a contact sheet. Three is not enough:
the flying mule was present at frame 15 and gone by frame 38.

### Lower cfg does NOT increase motion

A natural guess, and wrong for WAN 2.2. Measured on identical prompts and seeds:

| Variant | Motion index |
|---|---|
| shift 8.0, cfg 5.0 | 61.34 |
| shift 5.0, cfg 5.0 | 66.09 |
| **shift 8.0, cfg 4.0** | **50.15** |

Motion originates in the prompt, so weakening prompt adherence weakens the motion with
it. Leave cfg at 5.0. `shift` 5.0 buys a marginal increase but changes the sigma
schedule at native resolution, so it is not worth it without a reason.

### Measuring motion

"Does it move" is worth a number rather than an impression, and a frozen clip is easy
to mistake for a subtle one:

```bash
ffmpeg -v error -i clip.mp4 \
  -vf "tblend=all_mode=difference,lutyuv=y=val*20,scale=1:1,format=gray" \
  -f rawvideo - | python -c "import sys;b=sys.stdin.buffer.read()[1:];print(sum(b)/len(b))"
```

The `lutyuv` amplification is essential — without it, frame deltas average below 1 on a
0–255 scale and every clip scores 0.00 regardless of content. Values are relative:
0 is frozen, ~50 is a person walking, ~60 is lively ambient motion.

Beware the inverse error too: a degrading clip produces frame-to-frame differences that
*look* like camera movement in a contact sheet. Decay is not motion — measure it.

**The metric measures pixel change, not good animation.** Over one session it
misled me six times: it reported working clips as frozen (8-bit quantisation eats
sub-level motion — use the exact float method below), reported a frozen clip as
pristine, read progressive decay as camera movement, read smoothing after upscaling as
lost motion, ranked a drifting clip above a stable one, and ranked a clip with a flying
mule in it above the clean take.

Every one of those was settled in seconds by opening the frames. **Use the index to
detect frozen. Use your eyes for everything else.**

A clip whose framing wanders, or whose faces come apart, scores *high*. Two clips from
the same keyframe:

| | Motion | Frames 12/30/46 |
|---|---|---|
| shift 8.0 | 61.34 | framing slides, lamp drifts, face distorts by f46 |
| shift 5.0 | **66.09** | composition rock steady, flame and figures animate cleanly |

The higher score was also the better clip here — but for the opposite of the obvious
reason. Use the index to detect *frozen*; screen the frames to judge *good*.

### Upscaling: render small, upscale after

When a keyframe freezes at full resolution (see above), render at 704×384 where it
animates and upscale the finished clip. Confirmed working, 49 frames in 165s, no OOM:

```
LoadVideo -> GetVideoComponents -> ImageUpscaleWithModel -> ImageScale -> CreateVideo -> SaveVideo
```

- Model: **`RealESRGAN_x4plus_anime_6B.pth`** (18 MB). Trained on anime/cel art, not
  photographs — a photo-trained upscaler invents skin pores and fabric weave, which
  fights flat cel shading. This one reconstructs clean line edges and flat colour fields.
- **Upscale 4× then downsample to the 2× target**, rather than requesting 2× directly.
  The model gets more room to reconstruct edges and the downsample averages away its
  artefacts.
- Wire `CreateVideo.fps` from `GetVideoComponents` output 2 so the framerate carries
  through rather than being hardcoded.
- 704×384 → 1408×768 preserves the source's 11:6 aspect, slightly wider than 16:9.
  Conform in the edit.

Note the motion index drops after upscaling (66.09 → 46.51 measured) because the
downsample smooths pixel noise. The animation is unchanged — check frames, not the score.

### Use a stronger model for shots with hands or faces at scale

SDXL base, with or without IPAdapter, could not stage beat 01 in five attempts —
mother horizontal, child beside her, two figures held, correct ages. **Nano Banana 2
produced it correctly on the first try**, including clean hands, which is the failure
SDXL is most notorious for and which no amount of prompt work reliably fixes.

Hands in close-up are the specific case to outsource. A mangled hand is survivable in a
wide shot and fatal in a close-up.

Gemini prompting differs from SDXL's: write **prose, not keyword lists**, describe the
shot as a director would, and phrase exclusions as sentences at the end — there is no
negative prompt field. Ask explicitly for 16:9.

Style-matching caveat: a keyframe from a much stronger model may not cut with SDXL-sourced
neighbours. Either feed an approved keyframe in as a style reference, or regenerate the
whole set at the higher quality.

### Attribute bleed between characters

Beat 04 has Mara and Corren. Corren was described with "close-cropped grey hair and
short grey beard" — and **Mara came out white-haired**. A prompt's attributes are a
shared pool, not per-person assignments.

**Fix:** remove the competing attribute from the pool entirely. Corren is now "an older
weathered man in a long brown coat" with no hair colour at all. Better a generically
older man than a white-haired Mara.

### Subject-first ordering

Whatever the sentence opens on is what gets built. Open on Mara and you get a picture
of Mara with a scene fitted around her.

- ✗ "Mara stands on a ridge… beside her an older man points…" → Corren vanishes
- ✓ "Two figures stand together in wide shot on a high ridge…" → both present
- ✗ "…she stands looking down at a worn leather backpack" → no backpack
- ✓ "Wide landscape shot of a narrow supply track…" → Mara correctly small in frame

### Give a prop its own shot

The backpack in beat 05 failed **three times** across three phrasings, including being
made the grammatical subject and placed dead centre. SDXL will not reliably place a
small specific object inside a large scene.

Restaged as a **ground-level close-up with the pack filling the frame**, it worked
immediately — four of six candidates. It is also better filmmaking: a held shot on the
abandoned pack carries more than a wide with a speck in it.

**Rule:** if a prop matters, give it its own shot rather than placing it in someone
else's.

### Prompts leak their own palette

Beat 01 rendered as sepia line art. The prompt said *"warm amber light and deep black
shadows"* — two colours, one of them black. That is a monochrome instruction. Every
beat that rendered in full colour happened to contain several colour nouns (red rock,
burnt-orange sky, golden hour).

**Fix:** name a colour on every major surface — rust-red blanket, ochre canvas, olive
tunic, orange lamp flame, deep blue night. And put the failure in the negative:
`black and white, monochrome, greyscale, desaturated, sepia, line art, uncoloured,
colouring book page`.

This worked completely — nine of nine came back richly coloured. Two cautions from it:

- **It overcorrected to orange.** Naming a warm colour on most surfaces produced a
  near-monotone amber frame rather than the intended ochre/rust/slate-blue/olive
  spread. Name *contrasting* colours, not just warm ones — the cool surfaces need
  naming precisely because a lamplit scene won't invent them.
- **It cost the staging.** Adding ~20 negative tokens and lengthening the positive
  crowded out the two-figure composition that the previous pass had got right. See
  "One fix at a time" below.

### The palette clause is load-bearing for style

Trimming the style block from

> …thick black ink outlines, flat cel shading, hard-edged shadows, **limited palette of
> ochre, rust, slate blue and olive**, dramatic rim light, film grain

down to

> …thick black ink outlines, flat cel shading, hard-edged shadows, dramatic lamplight

sent every candidate into **stained glass / illuminated manuscript** — heavy black
leading, jewel tones, flat panels. The setting drifted with it: nomad tents became
four-poster beds in palace bedchambers.

"Thick black outlines + flat colour" describes stained glass as accurately as it
describes cel animation. The palette constraint was the thing disambiguating them.

**Treat the style block as a fixed unit.** Do not trim it for brevity. If a beat needs
different words, add them after it rather than editing inside it.

### Subject-first ordering applies to *people*, not just scenes

Two beat-01 passes lost the second figure for exactly this reason:

- Opening on "a dying woman lies flat on her back…" → a dying woman, alone
- Opening on "a nine-year-old girl… sits at her dying mother's bedside" → both present

Whoever the sentence opens on is who gets built. The other figure is optional as far
as the model is concerned. **Lead on the character who must not be dropped**, then give
the second character their own strong clause — a weak trailing mention ("her mother lies
still under a blanket") gets absorbed and reinterpreted.

### One fix at a time

Beat 01 has now flip-flopped: v5 had correct staging and no colour; v6 has correct
colour and lost the staging. Fixing two faults in one pass changed enough of the
prompt that a working part regressed.

When a candidate is *close*, prefer **img2img at moderate denoise (~0.35–0.45)** over
rewriting the prompt. It preserves the composition you already like and only repaints
surface qualities — exactly the right tool for "right shot, wrong colour".

### img2img preserves *who*, not just *where*

Tested on beat 01: correct staging (tent, mother horizontal, attendant kneeling), wrong
attendant (adult, dark-haired, where a red-haired nine-year-old was wanted). Swept
denoise 0.35 / 0.45 / 0.55 with the fault named explicitly in both prompt and negative.

**The figure did not change at any level.** All three outputs were near-identical, and
what changed was texture and lighting, not the person. A figure's identity is baked into
the latent structure and survives partial re-noise; the denoise needed to re-cast a
person is high enough to destroy the composition you were protecting.

Also useful: denoise below ~0.6 is **very** conservative for SDXL. A 0.35→0.55 sweep
produced barely distinguishable results — don't expect fine control in that range.

So img2img is the tool for palette, texture and lighting. It is **not** the tool for
changing who is in the shot. That needs a mask (inpaint the figure only) or a restage.

### When a figure won't behave, cut the shot tighter

Beat 05's backpack was rescued by giving the prop its own close-up. The same move
applies to people: a shot that doesn't need a face can't get the face wrong.

For beat 01 the strongest version may be a close-up on the hands alone — a child's two
small hands closed around a limp adult one on a blanket. No faces means no age problem
and no identity problem, and it is the most direct rendering of the lore, which says
Mara remembers her mother as *"the specific weight of her hand."*

Trade-off to weigh: a hands-only shot loses the girl's expression, which is real
dramatic content and not just decoration.

### Negative prompts are a repulsive force, not a filter

`vehicle` was in beat 05's negative and one candidate still produced **a motorcycle**.
`person` was in it and another produced two figures. Negatives shift probability; they
do not forbid.

This is the argument for generating 6+ candidates per beat rather than one-shotting.

### Watch for anachronism

Beat 06 v4 put **motor vehicles and a wooden shack** behind a pre-industrial character.
A model trained mostly on photographs pulls hard toward the modern world.

`car, truck, vehicle, machinery, power lines, road signs, modern building` is now in
the base negative for every beat.

### Read a stock negative prompt before pasting it

The WAN 2.2 template ships a negative containing `artwork, painting, style` — sensible
for photorealistic video, actively hostile to a hand-drawn cartoon. Those three are
stripped from all six beat workflows.

### Candidates beat iterations

Separate jobs with different seeds diversify more than one larger batch. Current
practice: **batch of 3 across 2–3 seeds = 6–9 candidates per beat.** Change the seed
before rewriting the prompt — seed variance is enormous and rewriting first means
chasing ghosts.

---

## IPAdapter tuning

IPAdapter solved character identity outright. Across four prompt-only passes Mara came
out auburn, orange, black-haired and in one case a different ethnicity. With IPAdapter
conditioned on her canonical game portrait, she is the same woman in every frame — and
the costume finally matches (blue-grey scarf, olive jacket, brown straps).

### The composition trade

At high weight it **eats the composition**. At weight ≥ 0.45 every beat collapsed into
the same medium close-up of Mara with a landscape behind — scenes, props and second
characters all gone. The one beat under 0.45 was the only one that kept its staging.

Two levers:

- **`weight`** — how hard identity is pushed
- **`start_at`** — IPAdapter's grip is strongest in early steps, and early steps decide
  composition. Starting *late* lets the prompt own framing while IPAdapter owns the face.

Use the basic **`IPAdapter`** node with `weight_type: "prompt is more important"`, fed by
`IPAdapterUnifiedLoader` on the `PLUS (high strength)` preset. That weight type is built
for this trade and is **not** available on `IPAdapterAdvanced`.

### Working values

| Beat | Weight | start_at | Note |
|---|---|---|---|
| 01 mother | 0.20 | 0.45 | She is nine; the reference is an adult |
| 02 father | 0.30 | 0.40 | Wide, she is small in frame |
| 03 pillar readers | 0.32 | 0.38 | Medium, among a group |
| 04 corren | 0.25 | 0.45 | Two-figure scene — one reference deletes the second person |
| 05 the pack | 0.18 | 0.50 | Lowest; no Mara in shot |
| 06 west | 0.35 | 0.35 | Full body, she is the subject |

Rule of thumb: **wider shot → lower weight and later start.** A portrait reference at
high weight drags any composition back toward portrait framing.

---

## The Mara chronicle

Six beats, 366 frames, 15.25s at 24fps. Lore sources:
`docs/lore/character-profiles/mara.md`, `corren.md`.

| # | Beat | Frames | Keyframe | Clip |
|---|---|---|---|---|
| 01 | Mother's death — the tent, age 9 | 49 | Nano Banana 2 | ✅ 1920×1080 HD |
| 02 | Father's death — the crushed cart, age 19 | 49 | Nano Banana 2 | in progress |
| 03 | The Pillar Readers — the dismissed carving | 49 | SDXL v4 | — |
| 04 | Corren — the ridge, age 23 | 73 | SDXL v4 | — |
| 05 | The abandoned pack — age 25 | 73 | SDXL v5 close-up | — |
| 06 | Walking west — age 27 | 61 | SDXL v5 | ✅ 1024×576 |

The two Nano Banana keyframes are markedly better than anything the SDXL + IPAdapter
pipeline produced across five passes, and they were first-try. Beats 03–05 should be
regenerated the same way; the SDXL set is the rough pass.

**Beat 02 restaging (2026-08-25):** "Mara standing near rubble" was too ambiguous — it
read as landscape-with-figure, not bereavement. It is now her father's **supply cart
crushed under the fall, with the mule alive and still harnessed nearby, head turned back
toward the wreck**. A cart does not drive itself; the animal got free and the driver did
not. That states a death without a body, in about half a second of screen time, and it
is specific to *him* — the lore defines her father almost entirely through his trade.

Deliberately not used: her holding an inherited object. Beat 05 is already "she finds
his abandoned pack", and two beats built on inherited objects in a 15-second film reads
as repetition, not rhyme.

### Staging notes

- **Beat 01** is her holding her mother's hand. Her profile says she remembers almost
  nothing of her mother except *"the smell of her hair and the specific weight of her
  hand"* — the hand is the memory that survived, so it should be the shot.
- **Beat 05** is a close-up on the pack alone. Per `corren.md` it is set down carefully,
  weighted with a flat stone, every strap fastened, no note and no body.
- **Beat 06** works best shot **from behind, walking away** — a stronger closing image
  for a montage about carrying a weight forward than the low hero angle first planned.

### Lore constraints observed

- Corren is **deliberate, not tragic**. If he went in without his pack it was a choice.
- Mara **does not weep**. Her register is watchful; the montage is unsentimental.
- The crucifix is **not** a Corren memorial — it sits outside her system entirely and
  appears only as present-day set dressing in beat 06.

### Open problem — timeline gap

The profile does not close arithmetically. Father dies at 19, two years with the Pillar
Readers, "two years" with Corren — but he vanished two years ago and she is 27. About
two years are unaccounted for. Beats currently use 23 for the mentorship and 25 for the
pack. Worth pinning down in `mara.md` if this becomes a series.

---

## Reference

### Resolution ladder

| Size | Frames | Status on the 2070 |
|---|---|---|
| 704 × 384 | 49 | Works. Motion 61.34. Use for probes |
| 1024 × 576 | 49–61 | Works. Motion 52.29. Detail degrades late in the clip |
| 1152 × 640 | 49 | Under test |
| 1280 × 704 | 33 | Under test |
| **1280 × 704** | **49** | ❌ **Frozen — VAE decode OOMs, all frames identical** |

WAN's native size is 1280×704, but 8 GB cannot hold it at 49 frames. The job reports
success and writes a valid file; only the pixels are wrong. **Verify motion after any
change to resolution or length** — see "Measuring motion".

Stills generate at **1344 × 768** (nearest real SDXL bucket to 16:9) and are Lanczos
scaled to 1024 × 576 to match the video latent.

### Settings

- **Stills:** 22 steps, cfg 7.0, dpmpp_2m / karras
- **Video:** 20 steps, cfg 5.0, uni_pc / simple, ModelSamplingSD3 shift 8

### Habits

- Press **R** in ComfyUI after any model file appears or disappears — dropdowns cache.
- Restart fully after installing a custom node. Model rescans are not enough.
- Record the seed of anything you like. There is no undo.

### Scripts

Generation scripts live in the session scratchpad and drive ComfyUI over its HTTP API
(`POST /prompt`) rather than the GUI, which makes batching and seed sweeps scriptable.
Worth relocating into the repo if this becomes a recurring workflow.
