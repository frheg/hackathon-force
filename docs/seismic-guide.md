# Seismic data guide

Everything we hold that is seismic, or that ties to seismic, measured on our own copies (19 November 2026).
Adele was scanned trace by trace (all 822,031 traces). F3 was read in full.

## 1. What seismic is, in one page

A ship tows a sound source (an air gun) and long cables of microphones (hydrophones). Sound goes down, bounces off
boundaries between rock layers, and comes back. A boundary reflects when the rock above and below differ in
**acoustic impedance** (density times sound speed). The recording at one surface point is a **trace**: amplitude
against **two-way time (TWT)**, the time down and back, in milliseconds. Time is not depth. Turning time into depth
needs a velocity model, usually checked against wells (**checkshots**, **VSP**).

A **3D survey** puts traces on a regular grid of **bins**. Rows of the grid in the sailing direction are **inlines**.
The rows at right angles are **crosslines** (xlines). So a 3D cube is indexed by (inline, crossline, time sample).

Processing before we get it: **stacking** averages many recordings of the same bin to beat down noise (a
**full offset stack** keeps all source to receiver distances). **Migration** moves the reflections to where they
really are, so dipping layers and faults sit in the right place. **PSTM** (pre-stack time migration) means migration
before stacking, with the result still in time.

What interpreters pick on it:
- **Horizons**: one reflector followed across the cube, usually a formation top.
- **Faults**: breaks where the layers are offset. They trap oil and gas, or leak it, and drillers must plan around
  them.
- **Facies**: zones that look alike in texture (layered, chaotic, transparent), standing for a rock type or setting.

## 2. Adele 3D (official, from the mail)

`data/official/adele/Adele_seismic_survey_NW australia_bind cube_fault_detection.segy`, 3.5 GB. Zenodo 4299758,
CC BY 4.0, credit Geoscience Australia. It is the FORCE 2020 fault competition's blind cube ("bind" in the file name
is a typo for blind): **it has no fault labels, horizons or wells.**

### Where and what

| Item | Value |
|---|---|
| Location | Offshore NW Australia, 13.67 to 13.78° S, 123.36 to 123.68° E (the text header writes degrees and minutes: 13°40′ to 13°46′ S) |
| Coordinate system | GDA94 / MGA zone 51 (UTM metres), X 539,114 to 573,239, Y 8,477,109 to 8,488,359 |
| Area | 34.1 km east-west by 11.3 km north-south, 384 km² |
| Product | `adele PSTM_FULL_OFFSET`: pre-stack time migrated, full offset stack, exported from Petrel 2019.4 on 30 June 2020 |
| Grid | 301 inlines (4175 to 4775, **every second one**) by 2,731 crosslines (5670 to 8400, every one) = 822,031 traces, a full rectangle |
| Bin size | 12.5 m between crosslines; 37.5 m between stored inlines (18.75 m per inline number) |
| Orientation | Inlines run east-west, crossline numbers growing westward; inline numbers grow northward |
| Time | 1,001 samples at 4 ms, **1,500 to 5,500 ms TWT** (a 4 s window; the first 1.5 s below the sea surface is not in the file) |
| Sample format | 4-byte IEEE float, big endian (SEG-Y format code 5) |

### The three headers in the file

A SEG-Y file is: a 3,200-byte **textual header** (40 lines of text), a 400-byte **binary header** (numbers for the
whole file), then for every trace a 240-byte **trace header** followed by the samples.

**Textual header** (C1 to C40): who wrote it, the inline and crossline ranges, the CRS, X/Y/lat/long ranges, the
amplitude range, the sample format, and a map of which bytes hold what. Petrel writes time as negative numbers
(-5502 to -1498); the trace headers use positive 1,500 to 5,500.

**Binary header**, the non-zero fields:

| Field (byte) | Value | Meaning |
|---|---|---|
| Interval (3217) | 4000 | Sample interval in microseconds: 4 ms |
| Samples (3221) | 1001 | Samples per trace |
| Format (3225) | 5 | IEEE float |
| SortingCode (3229) | 4 | Horizontally stacked: one trace per bin |
| EnsembleFold (3227) | 1 | One trace per bin after stacking |
| MeasurementSystem (3255) | 1 | Metres |
| ImpulseSignalPolarity (3257) | 1 | SEG normal polarity flag (treat with care; the processing history is not given) |
| JobID, LineNumber, ReelNumber, Traces, VerticalSum | 1 | Filler |

**Trace headers**, the fields that hold anything:

| Field | Bytes | Holds |
|---|---|---|
| INLINE_3D | 189 | Inline number, 4175 to 4775 (also copied in bytes 5 and 9) |
| CROSSLINE_3D | 193 | Crossline number, 5670 to 8400 (also in bytes 21 (CDP) and 1/13 as position in line) |
| CDP_X, CDP_Y | 181, 185 | Bin centre X and Y in centimetres (also copied in SourceX/Y, bytes 73 and 77) |
| SourceGroupScalar | 71 | -100: divide the coordinates by 100 to get metres |
| DelayRecordingTime, LagTimeA | 109, 105 | 1500: the first sample is at 1,500 ms |
| TRACE_SAMPLE_COUNT, TRACE_SAMPLE_INTERVAL | 115, 117 | 1001 samples, 4000 µs |
| TraceIdentificationCode | 29 | 1: live seismic data |
| CoordinateUnits | 89 | 1: length (metres) |
| The rest (DataUse, Correlated, SweepType, TaperType, TimeBaseCode, ElevationScalar) | | Constant 1, filler |

Read it with `segyio.open(path, iline=189, xline=193)`, or with the default byte positions, which match.

### What the amplitudes look like

| Measure | Value |
|---|---|
| Typical range | 98% of samples between -800 and +790; 99.9% inside about ±1,600 |
| Trace RMS | median 261 (1st to 99th percentile 170 to 428) |
| Header range | -350,841 to +266,022, **caused by one bad trace** |
| Spike | One trace, inline 4585, crossline 6071, a burst around 5,188 ms reaching -350,841 |
| Dead traces | 2,408 (0.29%): **the last 8 crosslines (8393 to 8400) are all zero on every inline** |
| Strength with time | RMS strong at the top (540 at 1.5 s), weak at 2.0 to 2.3 s (about 125), strongest at 3.7 to 4.2 s (about 420), fading below 4.5 s |
| Edges | The west end (high crosslines) is louder than the east end: median RMS 338 against 212 |
| Frequency | Peak 11 Hz; half power (-6 dB) 8.7 to 19.5 Hz; -20 dB 3.5 to 42 Hz; Nyquist 125 Hz |

What that means in practice:
- Clip at about ±1,500 (or the 99.9th percentile) before showing or training, else the spike sets the colour scale.
- Drop crosslines 8393 to 8400.
- The data is **low frequency** (deep and old). At 3,000 to 4,000 m/s a 11 Hz wavelet is about 270 to 360 m long,
  so beds thinner than about 70 to 90 m (a quarter wavelength, the **tuning thickness**) blur together. Faults with
  smaller throw than that are hard to see.
- Every second inline is missing, so the cube is coarser north-south (37.5 m) than east-west (12.5 m).

## 3. F3 Netherlands (found earlier, a stand-in)

`data/seismic/f3/data/`, 1.2 GB as numpy arrays. Zenodo 3755060, CC BY 4.0. It is the facies benchmark of Alaudah,
AlRegib et al. 2019 ("A machine learning benchmark for facies classification"), cut from the public F3 block in the
Dutch North Sea (released by dGB Earth Sciences). The geology is close to the southern Norwegian North Sea.

### Files

| File | Shape (inline, crossline, sample) | Type | Grid (original numbering) |
|---|---|---|---|
| `train/train_seismic.npy` | 401 × 701 × 255 | float64 | inlines 300 to 700, crosslines 300 to 1000 |
| `train/train_labels.npy` | same | uint8, 0 to 5 | |
| `test_once/test1_seismic.npy` (+ labels) | 200 × 701 × 255 | | inlines 100 to 299, same crosslines (beside the training block) |
| `test_once/test2_seismic.npy` (+ labels) | 601 × 200 × 255 | | inlines 100 to 700, crosslines 1001 to 1200 (the far side) |

There are no headers or coordinates: just the cube. Samples are 4 ms apart, so 255 samples is about one second of
TWT. Bins are 25 m.

Amplitudes are scaled to -1 to +1 (standard deviation about 0.21). The first sample of every trace is zero (that
is the 0.39% zero share). Energy spans about 4 to 41 Hz at half power, a wider band than Adele.

Also in the folder, built by our Seismic Lookalike tool: `index.npz` (patch index), `index.json` (its scores) and
`facies_clf.joblib` (the learned metric).

### The six labels

Every sample has a label: the rock unit it sits in. Shares are of all samples; depth is in sample index (0 = top).

| Label | Unit | Age and rock | Train | Test 1 | Test 2 | Where |
|---|---|---|---|---|---|---|
| 0 | Upper North Sea Group | Miocene to Quaternary clays and sands; big tilted delta foresets (clinoforms) | 28.1% | 19.2% | 24.1% | Top, samples 0 to 107 |
| 1 | Middle North Sea Group | Oligocene clays | 11.9% | 9.7% | 10.2% | A thin band, around sample 89 |
| 2 | Lower North Sea Group | Paleocene to Eocene clays and sands | 48.6% | 45.2% | 57.2% | The thick middle, around sample 166 |
| 3 | Rijnland Group / Chalk Group | Lower Cretaceous clays and sands, plus Upper Cretaceous chalk, merged | 6.6% | 7.0% | 5.0% | Around sample 219 |
| 4 | Scruff Group | Upper Jurassic to lowest Cretaceous marine clays | 3.3% | **17.1%** | 0.8% | Deep, around sample 232 |
| 5 | Zechstein Group | Upper Permian salt; it flows and makes domes | 1.5% | 1.9% | 2.7% | Deepest, thin in most traces |

What the labels tell you:
- It is nearly a **layer cake**: going down a trace the label never goes back to a younger unit, except in 46
  training traces and 69 test 1 traces (salt and fault areas).
- Classes are very **unbalanced**: Zechstein is 1.5% and Scruff 3.3% of training, so a model that ignores them
  still scores high pixel accuracy. Report per-class scores and mean IoU, not just accuracy.
- **Test 1 has five times more Scruff** than training. That shift is why our Lookalike tool scores 0.92 to 0.96
  on the Upper North Sea but 0.13 to 0.29 on Chalk, Scruff and Zechstein (chance 0.42 overall; 0.756 by texture,
  0.784 with the learned metric).

## 4. Seismic links in the other data

None of our wells sit inside either cube. But the well data holds what a seismic task needs to tie to wells:

| Source | What | How much |
|---|---|---|
| FORCE 2020 logs (`force2020/train.csv`) | `DTC` (compressional sonic, µs/ft), `RHOB` (density, g/cm³), `DTS` (shear sonic) | DTC on 93% of rows, RHOB 86%, DTS 15%; all 98 wells have both DTC and RHOB |
| Completion reports (`official/completion_reports`) | Pages on seismic, VSP, checkshots, TWT, synthetic seismograms, velocity surveys | In a sample of 300 reports (39,312 pages): "seismic" in 62% of reports, VSP 43%, TWT 30%, checkshot 26%, velocity survey 19%, synthetic seismogram 10% |
| FactPages formation tops | Depth of each formation per well | The depths a horizon pick ties to |

With DTC and RHOB a well gives a **synthetic seismogram**: velocity `Vp = 304,800 / DTC` m/s, acoustic impedance
`AI = RHOB × Vp`, reflection coefficient `(AI₂ - AI₁) / (AI₂ + AI₁)` at each step, convolved with a wavelet (an
11 Hz Ricker for Adele-like data). That is the bridge from logs to seismic.

Not here: Sodir's seismic survey list (FactPages has survey tables we have not fetched), and any NCS seismic cube.
KSAT is satellite radar (SAR) of the sea surface for oil slicks and seeps, not seismic; it comes at the event.

## 5. What each cube can and cannot do for a 2-day task

| | Adele | F3 |
|---|---|---|
| Labels | None (blind) | Six facies on every sample |
| Good for | Fault detection without labels: coherence or semblance attributes as a baseline, a fault model trained on synthetic data (FaultSeg3D style) applied to it, QC tools | Supervised facies segmentation with a known score; retrieval (our Lookalike tool) |
| Score it | Only by eye, or against faults you pick yourself | Mean IoU and per-class accuracy on test 1 and test 2 |
| Watch out | The spike, the 8 dead crosslines, missing alternate inlines, low frequency | Class imbalance, the test 1 shift, float64 arrays (convert to float32: half the memory) |

## 6. Terms

| Term | Meaning |
|---|---|
| Acoustic impedance (AI) | Density times P-wave velocity. Changes in AI make reflections |
| AGC | Automatic gain control: rescaling each window of a trace to even out loudness; destroys true amplitude |
| Amplitude | The strength of the recorded signal at a sample; here uncalibrated, only relative values mean anything |
| Bin | One cell of the 3D grid; one stacked trace per bin |
| CDP / CMP | Common depth point / common midpoint: the bin a group of recordings shares; used as a trace position |
| Checkshot | A tool in the well records the time for a surface shot to reach known depths: the time to depth link |
| Clinoform | A sloping layer at the front of a growing delta; very visible in F3's top unit |
| Coherence / semblance | An attribute measuring how alike neighbouring traces are; low where faults break the layers |
| Crossline (xline) | A row of the grid at right angles to the inlines |
| Dead trace | A trace of all zeros, no data |
| Dominant frequency | The frequency with the most energy; sets the resolution |
| Facies | A body of rock (or seismic texture) with a recognisable character |
| Fault / throw | A fracture where rock has moved; throw is the vertical offset |
| Full offset stack | A stack using all source to receiver distances |
| Horizon | One reflector traced across the survey |
| IEEE float / IBM float | Two ways of storing 4-byte numbers; SEG-Y format code 5 / code 1 |
| Inline | A row of the grid, normally along the sailing direction |
| IoU | Intersection over union: overlap of predicted and true area for a class, the usual segmentation score |
| Migration | Processing that moves reflections to their true position |
| Nyquist frequency | The highest frequency the sampling can hold: half the sampling rate (125 Hz at 4 ms) |
| Polarity | Whether a hard (impedance up) boundary shows as a positive or negative peak |
| PSTM / PSDM | Pre-stack time / depth migration; PSDM gives depth instead of time |
| Reflection coefficient | (AI below - AI above) / (AI below + AI above) |
| Ricker wavelet | A standard pulse shape used to model the seismic pulse |
| RMS amplitude | Root mean square: the average strength over a window |
| Salt dome / diapir | Salt that has flowed upward into a dome (F3's Zechstein) |
| Sample interval | Time between samples on a trace: 4 ms in both cubes |
| SEG-Y | The standard file format for seismic: textual header, binary header, then trace header plus samples per trace |
| Spike | A burst of absurd values, a recording or processing error |
| Stack | The average of many recordings of one bin |
| Synthetic seismogram | A trace computed from well logs, to compare with the real seismic at the well |
| Trace | The recording at one bin: amplitude against time |
| Tuning thickness | About a quarter wavelength; thinner beds blur into one reflection |
| TWT | Two-way time: down and back, in ms |
| VSP | Vertical seismic profile: receivers in the well record surface shots; a better checkshot |
| Wavelength | Velocity divided by frequency |


## 7. How finely the data is sampled (measured)

From `python -m sketches.atlas_seis resolution` and the Resolution page of the Atlas: average power spectrum and
autocorrelation along each axis of a block of each cube (Adele: 100 inlines x 800 crosslines x 600 samples, middle of
the cube; F3: the whole training block). "95 % below" is the wavenumber under which 95 % of the energy lies; Nyquist
is the finest detail the spacing can hold.

| Direction | Spacing | Nyquist | 95 % of energy below | Nyquist / that | Correlation drops to 0.5 at |
|---|---|---|---|---|---|
| Adele along an inline | 12.5 m | 40 cycles/km | 2.2 cycles/km | 18x | 207 m |
| Adele between inlines | 37.5 m | 13.3 cycles/km | 2.7 cycles/km | 5x | 170 m |
| Adele in time | 4 ms | 125 Hz | 28.8 Hz | 4.3x | 10 ms |
| F3 along / between inlines | 25 m | 20 cycles/km | 4.7 / 5.7 cycles/km | 4.3x / 3.5x | 149 / 138 m |
| F3 in time | 4 ms | 124.5 Hz | 40.2 Hz | 3.1x | 7 ms |

What follows from it:
- Both cubes are sampled finer than their content needs, in every direction. Adele's 37.5 m between stored inlines
  still holds the signal with 5x to spare, so the missing inlines cost little for smooth reflectors; narrow features
  such as faults are where they could matter.
- Adele could be thinned in time to 8 ms with almost no loss (0.09 % of the energy lies above half of Nyquist).
- Rock per sample is about 7 m (Adele, assumed 3,500 m/s) and 4 m (F3, assumed 2,000 m/s). The speeds are
  assumptions: nothing in the cubes measures them.
- Resolution is set by the sound, not the grid: an 11 Hz pulse at 3,500 m/s has a 313 m wavelength, so layers thinner
  than about 78 m (a quarter wavelength) blur together and a 10 m fault throw is below detection.
- A 128 x 128 x 128 patch of Adele covers 1.6 km x 4.8 km x 512 ms: the voxels are 12.5 x 37.5 m wide and about 7 m
  tall, so resample before training (interpolate inlines 3x, thin time to 8 ms: 901 x 2,731 x 501 voxels, 4.9 GB as
  float32).

## 8. What stands out in Adele (measured, 19 November 2026)

From coherence on every 40th time slice, the spectrum in 1-second windows, and loudness by third of the survey.

- **Resolution is not one number: it changes a lot with depth.** Half of the energy lies at 8 to 45 Hz between 1.5 and
  2.5 s, 8 to 23 Hz at 2.5 to 3.5 s, and only 9 to 18 Hz at 3.5 to 4.5 s (usable up to 75, 51 and 34 Hz). The shallow
  section resolves much thinner layers than the deep one. The average peak of 11 Hz is set by the deep, strong part.
- **A strong amplitude package at 3.5 to 4.5 s that fades to the east.** RMS is 496 in the western third, 387 in the
  middle and 247 in the eastern third; at 4.5 to 5.5 s it is 263, 197 and 159. Shallower than 3.5 s the three thirds
  agree within about 15 %. A lateral amplitude change like this can mean a change of rock, of fluid, or of processing;
  the cube cannot say which, but it is the most obvious thing to investigate.
- **Faults are sparse.** Only 0.5 to 1 % of any time slice is strongly discontinuous (above 0.6), except at the top
  and bottom edge of the window (3 to 4 %, an edge effect of the filter).
- **The "most broken" interval is a weak-signal interval.** Mean discontinuity peaks at 2.1 to 2.3 s (0.20, strongest in
  the west and middle), exactly where the loudness is lowest (RMS about 125). Weak data is noisy, so low coherence
  there is at least partly noise, not faults. Check on the section before believing it.
- **The upper section is nearly flat.** The mean reflector dip in a 2.5 to 3.7 s block (inlines 4375 to 4573,
  crosslines 6670 to 7469) is about 3 degrees, so the folding and dipping seen below 3.5 s is a different structural
  style from what lies above it.
