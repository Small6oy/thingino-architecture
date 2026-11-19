#!/usr/bin/env python3
"""Generate cameras.json from Thingino's own camera configs.

    python3 import_cameras.py             read the thingino-firmware checkout ($THINGINO_FIRMWARE or ../thingino-firmware)
    python3 import_cameras.py --firmware DIR
    python3 import_cameras.py --fetch     git fetch --all in the checkout first
    python3 import_cameras.py --testing   also include configs/cameras-testing

For every firmware version in architecture.toml, the version's git `ref` decides
which camera configs it ships (stable: configs/cameras, experimental:
configs/cameras-exp). Each camera's facts come from its defconfig and
thingino.json in the newest version that has it; SoC facts (family, CPU
architecture, RAM) come from Thingino's SoC database (soc/ingenic/*.mk) and
the kernel from kernels/ingenic.mk, both read at the first version's ref.

Hand-checked facts in architecture.toml [[cameras]] (same id) override these
fields at build time; build.py does the merge.

Not in Thingino's configs, so not generated: sensor resolution, CPU clock,
the video-memory split (unless the config sets BR2_THINGINO_RMEM_MB).

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "cameras.json"
def _default_firmware() -> Path:
    """A thingino-firmware checkout: $THINGINO_FIRMWARE, else ../thingino-firmware next to this repo,
    else ../../../projects/thingino-firmware (the author's workspace layout)."""
    import os
    if os.environ.get("THINGINO_FIRMWARE"):
        return Path(os.environ["THINGINO_FIRMWARE"]).expanduser()
    for cand in (HERE.parent / "thingino-firmware", HERE.parents[2] / "projects" / "thingino-firmware"):
        if (cand / ".git").exists():
            return cand
    return HERE.parent / "thingino-firmware"


DEFAULT_FIRMWARE = _default_firmware()
TIERS = {"cameras": "stable", "cameras-exp": "experimental", "cameras-secureboot": "secure boot"}

ARCH_CPU = {"xburst1": "XBurst1, 1 core", "xburst2": "XBurst2, 2 cores"}
# Encoders by family. Only what's certain; the rest say "hardware video + JPEG".
FAMILY_ENCODER = {
    "t10": "H.264 + JPEG", "t20": "H.264 + JPEG",
    "t21": "H.264/H.265 + JPEG", "t30": "H.264/H.265 + JPEG", "t31": "H.264/H.265 + JPEG",
    "t40": "H.264/H.265 + JPEG", "t41": "AVPU (H.264/H.265) + JPEG",
}
NNA_FAMILIES = {"t40", "t41"}          # SoCs with a neural-network accelerator
SKIP_FAMILIES = {"a1": "no ISP or sensor (a media processor)"}
SKIP_WIFI = {"hwsim": "simulated Wi-Fi (test/emulator config)"}


def git(fw: Path, *args: str) -> str | None:
    r = subprocess.run(["git", "-C", str(fw), *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


class Blobs:
    """Read many files at many refs through one `git cat-file --batch` process (fast on a network share)."""
    def __init__(self, fw: Path):
        self.p = subprocess.Popen(["git", "-C", str(fw), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def show(self, ref: str, path: str) -> str | None:
        self.p.stdin.write(f"{ref}:{path}\n".encode()); self.p.stdin.flush()
        header = self.p.stdout.readline().decode().split()
        if len(header) < 3 or header[1] == "missing":
            return None
        size = int(header[2])
        data = self.p.stdout.read(size); self.p.stdout.read(1)   # trailing newline
        return data.decode(errors="replace") if header[1] == "blob" else None


# ---------------------------------------------------------------- SoC database
def soc_database(fw: Path, ref: str) -> dict[str, dict]:
    """model -> {family, arch, ram_mb}, parsed from soc/ingenic/<family>.mk."""
    db = {}
    files = (git(fw, "ls-tree", "--name-only", ref, "soc/ingenic/") or "").split()
    for f in files:
        text = git(fw, "show", f"{ref}:{f}") or ""
        models = re.search(r"\$\(filter \$\(SOC_MODEL\),([^)]*)\)", text)
        if not models:
            continue
        models = models.group(1).split()
        common = {"family": None, "arch": None, "ram_mb": None}
        per, current, default = {}, None, {}
        for line in text.splitlines():
            line = line.strip()
            m = re.match(r"(?:else\s+)?ifeq \(\$\(SOC_MODEL\),(\w+)\)", line)
            if m:
                current = per.setdefault(m.group(1), {}); continue
            if line == "else":
                current = default; continue
            if line == "endif" and current is not None:
                current = None; continue
            m = re.match(r"SOC_(FAMILY|ARCH|RAM_MB)\s*:=\s*(\S+)", line)
            if m:
                key = {"FAMILY": "family", "ARCH": "arch", "RAM_MB": "ram_mb"}[m.group(1)]
                (current if current is not None else common)[key] = m.group(2)
        for model in models:
            entry = dict(common)
            entry.update({k: v for k, v in (per.get(model) or default).items() if v})
            db[model] = entry
    return db


def kernel_defaults(fw: Path, ref: str) -> dict[str, str]:
    text = git(fw, "show", f"{ref}:kernels/ingenic.mk") or ""
    m = re.search(r"ifeq \(\$\(SOC_ARCH\),xburst2\)\s*KERNEL_VERSION := (\S+)\s*else\s*KERNEL_VERSION := (\S+)", text)
    return {"xburst2": m.group(1), "xburst1": m.group(2)} if m else {"xburst2": "4.4.94", "xburst1": "3.10.14"}


# ---------------------------------------------------------------- configs
def list_configs(fw: Path, ref: str, tiers: dict[str, str]) -> dict[str, tuple[str, str]]:
    """config name -> (tier folder, tier label) for one ref."""
    out = {}
    for folder, label in tiers.items():
        for name in (git(fw, "ls-tree", "-d", "--name-only", ref, f"configs/{folder}/") or "").split():
            out[Path(name).name] = (folder, label)
    return out


def parse_defconfig(text: str) -> dict:
    cfg = {"_name": None, "_frag": ""}
    for line in text.splitlines():
        if line.startswith("# NAME:"):
            cfg["_name"] = line.split(":", 1)[1].strip()
        elif line.startswith("# FRAG:"):
            cfg["_frag"] = line.split(":", 1)[1].strip()
        else:
            m = re.match(r"([A-Z0-9_]+)=(.*)", line.strip())
            if m:
                cfg[m.group(1)] = m.group(2).strip().strip('"')
    return cfg


def camera_from(name: str, tier: str, cfg: dict, tjson: dict, socdb: dict, kdef: dict) -> tuple[dict | None, str]:
    model = (cfg.get("BR2_INGENIC_SOC_MODEL") or "").lower()
    if not model:
        legacy = [k for k in cfg if k.startswith("BR2_SOC_INGENIC_") and cfg[k] == "y"]
        model = legacy[0].removeprefix("BR2_SOC_INGENIC_").lower() if legacy else ""
    if cfg.get("BR2_SIGMASTAR_SOC_MODEL") or not model:
        return None, "not an Ingenic SoC"
    soc = socdb.get(model)
    if not soc:
        return None, f"SoC '{model}' not in the SoC database"
    family, arch = soc["family"], soc["arch"]
    if family in SKIP_FAMILIES:
        return None, SKIP_FAMILIES[family]
    wifi_pkgs = [k.removeprefix("BR2_PACKAGE_WIFI_") for k, v in cfg.items()
                 if k.startswith("BR2_PACKAGE_WIFI_") and v == "y" and not k.startswith("BR2_PACKAGE_WIFI_FW")]
    wifi_pkgs = [w for w in wifi_pkgs if w not in ("", "Y")]
    if any(w.lower() in SKIP_WIFI for w in wifi_pkgs):
        return None, SKIP_WIFI["hwsim"]

    title = cfg["_name"] or name
    paren = re.match(r"(.*?)\s*\((.*)\)\s*$", title)
    model_name = paren.group(1) if paren else title
    parts = [p.strip() for p in paren.group(2).split(",")] if paren else []
    sensors = [cfg[k].upper() for k in sorted(cfg) if re.fullmatch(r"BR2_SENSOR_\d+_NAME", k) and cfg[k]]
    eth = cfg.get("BR2_ETHERNET") == "y"
    if wifi_pkgs:
        driver = wifi_pkgs[0].lower()
        chip = parts[-1] if len(parts) >= 3 else wifi_pkgs[0]
        wifi, wifi_short = chip, chip
    else:
        driver, wifi, wifi_short = "none", "none (wired Ethernet)" if eth else "none", "none"
    ram = int(soc["ram_mb"]) if soc.get("ram_mb") else None
    rmem = int(cfg["BR2_THINGINO_RMEM_MB"]) if cfg.get("BR2_THINGINO_RMEM_MB", "").isdigit() else None
    if ram and rmem:
        ram_txt = f"{ram} MB: {ram - rmem} MB Linux + {rmem} MB video"
    else:
        ram_txt = f"{ram} MB" if ram else "unknown"
    kernel = "4.4.94" if cfg.get("KERNEL_VERSION_4") == "y" else "3.10.14" if cfg.get("KERNEL_VERSION_3") == "y" else kdef[arch]
    flash = cfg.get("FLASH_SIZE_MB")
    nand = cfg.get("BR2_THINGINO_FLASH_NAND") == "y" or "flash-nand" in cfg["_frag"]
    gpio = (tjson or {}).get("gpio", {})

    features = []
    for flag, feat in (("BR2_THINGINO_AUDIO", "audio"), ("BR2_THINGINO_SDCARD", "sd"),
                       ("BR2_THINGINO_MOTORS", "ptz"), ("BR2_PACKAGE_THINGINO_MOTORS", "ptz"),
                       ("BR2_ETHERNET", "eth"), ("BR2_THINGINO_PWM_ENABLE", "pwm")):
        if cfg.get(flag) == "y" and feat not in features:
            features.append(feat)
    if wifi_pkgs:
        features.append("wifi")
    if "ircut" in gpio:
        features.append("ircut")
    if family in NNA_FAMILIES:
        features.append("nna")
    if len(sensors) > 1:
        features.append("multisensor")

    return {
        "id": name,
        "name": title,
        "model": model_name,
        "group": model_name.split()[0] if model_name else name.split("_")[0].title(),
        "tier": tier,
        "image": name,
        "soc": f"Ingenic {model.upper()}",
        "soc_family": family,
        "arch": arch,
        "cpu": ARCH_CPU.get(arch, arch),
        "sensor": " + ".join(sensors) if sensors else "unknown",
        "ram": ram_txt,
        "flash": f"{flash} MB SPI {'NAND' if nand else 'NOR'}" if flash else ("SPI NAND" if nand else "unknown"),
        "wifi": wifi,
        "wifi_short": wifi_short,
        "wifi_driver": driver,
        "kernel": kernel,
        "isp_module": f"tx_isp_{family}",
        "encoder": FAMILY_ENCODER.get(family, "hardware video + JPEG"),
        "features": features,
        "source": "Thingino config",
    }, ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--firmware", default=str(DEFAULT_FIRMWARE), help="thingino-firmware checkout")
    ap.add_argument("--fetch", action="store_true", help="git fetch --all first")
    ap.add_argument("--testing", action="store_true", help="include configs/cameras-testing")
    args = ap.parse_args()
    fw = Path(args.firmware).expanduser()
    if not (fw / ".git").exists():
        sys.exit(f"{fw} is not a git checkout of thingino-firmware")
    if args.fetch:
        print("fetching ...")
        subprocess.run(["git", "-C", str(fw), "fetch", "--all", "--quiet"])
    tiers = dict(TIERS, **({"cameras-testing": "testing"} if args.testing else {}))

    versions = tomllib.loads((HERE / "architecture.toml").read_text())["versions"]
    refs = [(v["id"], v.get("ref") or "HEAD") for v in versions]
    newest_ref = refs[0][1]
    socdb, kdef = soc_database(fw, newest_ref), kernel_defaults(fw, newest_ref)
    if not socdb:
        sys.exit(f"no SoC database at {newest_ref}:soc/ingenic/")

    per_version = {vid: list_configs(fw, ref, tiers) for vid, ref in refs}
    blobs = Blobs(fw)
    cameras, skipped = {}, {}
    for vid, ref in refs:                      # newest first: its facts win
        for name, (folder, tier) in sorted(per_version[vid].items()):
            if name in cameras or name in skipped:
                continue
            defconf = blobs.show(ref, f"configs/{folder}/{name}/{name}_defconfig")
            if defconf is None:   # some folders name the file differently
                files = (git(fw, "ls-tree", "--name-only", ref, f"configs/{folder}/{name}/") or "").split()
                other = [f for f in files if f.endswith("_defconfig") or f.endswith("/defconfig")]
                defconf = blobs.show(ref, other[0]) if other else None
            if defconf is None:
                skipped[name] = "no defconfig"; continue
            tj = blobs.show(ref, f"configs/{folder}/{name}/thingino.json")
            try:
                tjson = json.loads(tj) if tj else {}
            except json.JSONDecodeError:
                tjson = {}
            cam, why = camera_from(name, tier, parse_defconfig(defconf), tjson, socdb, kdef)
            if cam:
                cameras[name] = cam
            else:
                skipped[name] = why
    for cam in cameras.values():
        cam["supports"] = [vid for vid, _ in refs if cam["id"] in per_version[vid]]

    ordered = sorted(cameras.values(), key=lambda c: (c["group"].lower(), c["name"].lower()))
    source = {vid: {"ref": ref, "commit": (git(fw, "rev-parse", "--short", ref) or "").strip(),
                    "date": (git(fw, "log", "-1", "--format=%cs", ref) or "").strip(),
                    "configs": len(per_version[vid])} for vid, ref in refs}
    OUT.write_text(json.dumps({"_generated_by": "import_cameras.py", "_source": source,
                               "_skipped": dict(sorted(skipped.items())), "cameras": ordered},
                              indent=1, ensure_ascii=False) + "\n")
    by_tier = {}
    for c in ordered:
        by_tier[c["tier"]] = by_tier.get(c["tier"], 0) + 1
    print(f"wrote {OUT.name}: {len(ordered)} cameras ({', '.join(f'{n} {t}' for t, n in by_tier.items())}), "
          f"{len(skipped)} skipped")
    for vid, s in source.items():
        print(f"  {vid}: {s['ref']} @ {s['commit']} ({s['date']}), {s['configs']} configs")
    reasons = {}
    for why in skipped.values():
        reasons[why] = reasons.get(why, 0) + 1
    for why, n in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  skipped {n}: {why}")


if __name__ == "__main__":
    main()
