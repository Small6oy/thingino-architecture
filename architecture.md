# Thingino architecture diagram

An interactive page that shows how Thingino works on a given camera and firmware version. It covers the hardware, kernel drivers, libimp (and raptor-hal), the streamer, the network and where the stream ends up. It also includes the boot order and the upstream repo behind each piece. Pick a camera and a firmware version at the top; the diagram, text, boot steps and repo pins all change to match.

**Open it:** three layouts of the same data, each one self-contained file you can double-click:

| Page | Layout | Good for |
|---|---|---|
| [architecture.html](architecture.html) | **A · Stacked lanes**: the canvas diagram, top to bottom, animated packets | The whole system at a glance |
| [architecture-signal.html](architecture-signal.html) | **B · Signal Path**: left-to-right signal chain in a blueprint style, ports and wires, side drawer, "whole path" tracing, boot steps on an S00–S99 ruler | Following one signal end to end |
| [architecture-explorer.html](architecture-explorer.html) | **C · Explorer**: app with a searchable parts list, stack minimap, focus graph (inputs, part, outputs), back history, and tabs for journey, boot and sources | Learning part by part |

A view can be linked directly: `architecture.html#<camera config>+<version>`, for example `architecture.html#wyze_cam3_t31x_gc2053_rtl8189ftv+thingino1`.

**Scope:** generic Thingino only. No household data (IPs, hostnames, NVR servers, personal forks or add-ons such as rhkd). Camera docs elsewhere in `research/thingino/` hold that.

## Files

| File | What it is | Edit it? |
|---|---|---|
| `architecture.toml` | **All the content**: versions, lanes, boxes, connections, boot and journey steps, repos, and hand-checked camera facts | Yes, this is where changes go |
| `import_cameras.py` | Reads Thingino's camera configs and writes `cameras.json` | When Thingino's config format changes |
| `cameras.json` | Every Thingino camera config as data (generated, committed) | No: re-run the importer |
| `template.html`, `template-signal.html`, `template-explorer.html` | One template per layout: look and behaviour only | To change a layout |
| `core.js` | Shared data logic every layout uses: conditions, variants, placeholders, markup, path tracing. build.py adds it to each template at `/*__CORE__*/` | When the data model changes |
| `build.py` | The engine: merges the cameras, checks every camera × version view, refreshes pins, writes the pages | Rarely |
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
python3 import_cameras.py     # regenerate cameras.json from the same checkout (about 30 s on the share)
```

Python 3.11+ with the standard library only (uses `tomllib`). Each build prints a summary such as `467 camera x version views checked; 18-46 boxes, 15-52 lines`.

**Adding a layout:** copy a template, keep `/*__CORE__*/` and `/*__DATA__*/null`, build the page from `TC.view(DATA, cam, ver)`, and add a line to `LAYOUTS` in build.py.

## The model

| Concept | Where | What it does |
|---|---|---|
| **Camera** | `cameras.json` + `[[cameras]]` | One Thingino camera config (board + sensor + Wi-Fi chip), id = the config name. `import_cameras.py` generates every field from Thingino's configs; a `[[cameras]]` entry with the same id overrides fields with facts checked on hardware. `group` (the vendor) groups the picker; `features` drive `needs` and variants; `supports` lists the versions that ship the config. |
| **Version** | `[[versions]]` | A firmware line: name, codename, core streamer, and the git `ref` that `--pins` reads package pins from. |
| **Conditions** | on any lane, box, line, step or repo | `versions = [...]`, `cameras = [...]`, `needs = ["nna"]`. Nothing set means it shows everywhere. A hidden lane hides its boxes; a hidden box hides its lines; empty lanes disappear. |
| **Placeholders** | in any text | `{camera.sensor}`, `{version.core}` and so on. They fill in from the selected camera and version. `{camera.resolution?}` is optional: empty when a camera lacks the field, and a spec row that comes out empty is dropped. |
| **Variants** | `[<item>.variant.<key>]` right after an item | Overrides fields when the key matches: a version id, a camera feature (e.g. `nna`) or a camera id, applied in that order. |
| **Layout** | lanes | Boxes fill a lane's columns left to right. `cols = "auto"` sizes the lane to the boxes shown (at least `min_cols`). `col` and `span` place a box by hand. |

## Where the cameras come from

`import_cameras.py` reads the thingino-firmware checkout at each version's `ref` (`upstream/master`, `upstream/ciao`), so it works offline and matches exactly what each line ships:

| Field | Source in thingino-firmware |
|---|---|
| name, model, vendor group | `# NAME:` line of `configs/<tier>/<config>/<config>_defconfig` |
| tier | the folder: `cameras` = stable, `cameras-exp` = experimental, `cameras-secureboot` = secure boot (`--testing` adds `cameras-testing`) |
| SoC, sensor(s), Wi-Fi driver, flash size and NAND, video memory | `BR2_INGENIC_SOC_MODEL`, `BR2_SENSOR_<n>_NAME`, `BR2_PACKAGE_WIFI_*`, `FLASH_SIZE_MB`, `BR2_THINGINO_FLASH_NAND`, `BR2_THINGINO_RMEM_MB` |
| features | `BR2_THINGINO_AUDIO` → audio, `_SDCARD` → sd, `_MOTORS` → ptz, `BR2_ETHERNET` → eth, `_PWM_ENABLE` → pwm, a Wi-Fi package → wifi, `gpio.ircut` in `thingino.json` → ircut, T40/T41 → nna, two sensors → multisensor |
| SoC family, CPU architecture, RAM | the SoC database `soc/ingenic/<family>.mk` |
| kernel | `KERNEL_VERSION_4` / `_3` in the defconfig, else the default per architecture in `kernels/ingenic.mk` |
| supports | which versions' refs have the config folder |

Thingino's configs don't record sensor resolution or CPU clock, so those show only for cameras with a hand-checked `[[cameras]]` entry (today the Wyze Cam v3 and v4). Skipped: non-Ingenic SoCs, the A1 (a media processor with no sensor), simulated Wi-Fi, and folders without a defconfig. The importer prints what it skipped and why, and lists it under `_skipped` in `cameras.json`.

On 2026-11-19 that gave **246 cameras** (186 stable, 59 experimental, 1 secure boot): 208 on both lines, 26 on Thingino 2 only, 11 on Ciao only.

## Recipes

- **New cameras upstream:** `python3 import_cameras.py --fetch`, then `python3 build.py`.
- **Correct or add a camera fact** (resolution, CPU clock, a better chip name): add a `[[cameras]]` block with the config name as `id` and only the fields to override.
- **New hardware feature** (say, a floodlight): teach `import_cameras.py` the config flag, then add boxes with `needs = ["<feature>"]`.
- **Add a firmware version:** copy a `[[versions]]` block with a new `id` and `ref`, then run `python3 import_cameras.py` (fills `supports`) and `python3 build.py --pins`. Mark anything that only exists in it with `versions = ["<id>"]`, and use `[<item>.variant.<id>]` where only the wording changes.
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
- Some config names contain `+` (e.g. `..._eth+atbm6031`). Page links split on the **last** `+`, so `#<camera>+<version>` still works.
- Generated facts are only as good as the configs: a chip name comes from the `# NAME:` line when it has three parts, otherwise from the Wi-Fi package name.
- The boot order comes from the thingino-firmware and raptor sources, not from a live camera.

## Sources

The raptor README and `config/S31raptor` (`workspace/projects/raptor`), thingino-firmware `package/*/*.mk` and init scripts at `upstream/master` and `upstream/ciao`, `package/thingino-daynightd/files/README.md`, the camera configs and SoC database described above, and [../camera-stats.md](../camera-stats.md) for the hand-checked Wyze facts.
