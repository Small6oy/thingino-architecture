# Thingino architecture diagram

An interactive page that shows how Thingino works on a given camera and firmware version. It covers the hardware, kernel drivers, libimp (and raptor-hal), the streamer, the network and where the stream ends up. It also includes the boot order and the upstream repo behind each piece. Pick a camera and a firmware version at the top; the diagram, text, boot steps and repo pins all change to match.

**Open it:** three layouts of the same data, each one self-contained file you can double-click:

| Page | Layout | Good for |
|---|---|---|
| [architecture.html](architecture.html) | **A · Stacked lanes**: the canvas diagram, top to bottom, animated packets | The whole system at a glance |
| [architecture-signal.html](architecture-signal.html) | **B · Signal Path**: left-to-right signal chain in a blueprint style, ports and wires, side drawer, "whole path" tracing, boot steps on an S00–S99 ruler | Following one signal end to end |
| [architecture-explorer.html](architecture-explorer.html) | **C · Explorer**: app with a searchable parts list, stack minimap, focus graph (inputs, part, outputs), back history, and tabs for journey, boot and sources | Learning part by part |

A view can be linked directly, for example `architecture-explorer.html#wyze-cam-v3+thingino1`.

**Scope:** generic Thingino only. No household data (IPs, hostnames, NVR servers, personal forks or add-ons such as rhkd). Camera docs elsewhere in `research/thingino/` hold that.

## Files

| File | What it is | Edit it? |
|---|---|---|
| `architecture.toml` | **All the content**: cameras, versions, lanes, boxes, connections, boot and journey steps, repos | Yes, this is where changes go |
| `template.html`, `template-signal.html`, `template-explorer.html` | One template per layout: look and behaviour only | To change a layout |
| `core.js` | Shared data logic every layout uses: conditions, variants, placeholders, markup, path tracing. build.py adds it to each template at `/*__CORE__*/` | When the data model changes |
| `build.py` | The engine: checks every camera × version view, refreshes pins, writes the page | Rarely |
| `pins.json` | Commit pins per version, read by `--pins` (generated) | No |
| `architecture*.html` | The finished pages (generated, overwritten on every build) | **No** |

## Commands

```sh
cd research/thingino/architecture
python3 build.py              # check every view and write architecture.html
python3 build.py --open       # same, then open it
python3 build.py --watch      # rebuild on every save of the .toml or the template
python3 build.py --check      # check only
python3 build.py --pins       # re-read pins for every version from workspace/projects/thingino-firmware
python3 build.py --pins --fetch   # git fetch --all first, so upstream refs are current
```

Python 3.11+ with the standard library only (uses `tomllib`). Each build prints one line per view, for example `wyze-cam-v3 + thingino1: 25 boxes, 21 lines`.

**Adding a layout:** copy a template, keep `/*__CORE__*/` and `/*__DATA__*/null`, build the page from `TC.view(DATA, cam, ver)`, and add a line to `LAYOUTS` in build.py.

## The model

| Concept | Where | What it does |
|---|---|---|
| **Camera** | `[[cameras]]` | One Thingino camera config (board + sensor + Wi-Fi chip). It holds hardware facts used by placeholders, a `group` (the model, which groups the picker), `features` (e.g. `nna`) and `supports` (the versions that ship a config for it). |
| **Version** | `[[versions]]` | A firmware line: name, codename, core streamer, and the git `ref` that `--pins` reads package pins from. |
| **Conditions** | on any lane, box, line, step or repo | `versions = [...]`, `cameras = [...]`, `needs = ["nna"]`. Nothing set means it shows everywhere. A hidden lane hides its boxes; a hidden box hides its lines; empty lanes disappear. |
| **Placeholders** | in any text | `{camera.sensor}`, `{version.core}` and so on. They fill in from the selected camera and version. |
| **Variants** | `[<item>.variant.<id>]` right after an item | Overrides fields for one version or camera id. Version variants apply first, then camera variants. |
| **Layout** | lanes | Boxes fill a lane's columns left to right. `cols = "auto"` sizes the lane to the boxes shown (at least `min_cols`). `col` and `span` place a box by hand. |

Today the data covers what we have real facts for: **Wyze Cam v4 (OS04D10)** and **Wyze Cam v3 (RTL8189FTV)**, each on **Thingino 2 "Figata" (raptor)** and **Thingino 1 "Ciao" (prudynt)**. Both versions ship configs for both cameras.

## Recipes

- **Add a camera** (for example the v3's ATBM6031 variant): copy a `[[cameras]]` block, give it a new `id`, keep the same `group`, and change the facts. The build fails if a field used by a placeholder is missing. If it has hardware nothing else has (PTZ motors, Ethernet), add a feature such as `"ptz"`, then add boxes with `needs = ["ptz"]`.
- **Add a firmware version:** copy a `[[versions]]` block with a new `id` and `ref`. Add the id to each camera's `supports`, then run `python3 build.py --pins`. Mark anything that only exists in it with `versions = ["<id>"]`, and use `[<item>.variant.<id>]` where only the wording changes.
- **Add a daemon:** add a `[[nodes]]` block (with `versions = [...]` if it's version-specific) and its lines under `[connections]`.
- **Thingino moves on:** `python3 build.py --pins --fetch`.

## What the build checks

The build covers every supported camera × version view. If anything is wrong it stops, lists every problem, and writes nothing. It catches:

- placeholders that a camera or version lacks
- unknown ids in conditions, variants, lines, `upstream` or `supports`
- boxes that overlap or overflow a lane in any view
- bad colours or line kinds
- a camera id that clashes with a version id

It warns about boxes or lines that never show in any view, boxes with no lines (mark intended ones `standalone = true`), versions without pins, and titles too long for the canvas.

## Gotchas

- In TOML, a plain `key = value` after a `[[nodes]]` block belongs to **that node**. That's why the edge list sits under its own `[connections]` header, and why a variant table must come straight after its item.
- `--pins` reads each version's `ref` with `git show`. Refs like `upstream/master` only move when you fetch (`--fetch`).
- Thingino has more configs for these models (v3: T31AL/ATBM6031, RT5370; v4: GC4653 sensor). Add them as cameras once their facts are known.
- The boot order comes from the thingino-firmware and raptor sources, not from a live camera.

## Sources

The raptor README and `config/S31raptor` (`workspace/projects/raptor`), thingino-firmware `package/*/*.mk` and init scripts at `upstream/master` and `upstream/ciao`, `package/thingino-daynightd/files/README.md`, and [../camera-stats.md](../camera-stats.md) for the hardware facts.
