# Thingino architecture diagram

An interactive, data-driven diagram of how a [Thingino](https://thingino.com/) camera works: hardware, kernel drivers, libimp and raptor-hal, the streamer daemons, shared-memory rings, consumers, network and outputs. You pick a camera and a firmware version, and the diagram, boot order and upstream repo pins follow.

**Open it: <https://small6oy.github.io/thingino-architecture/>** (also [Signal Path](https://small6oy.github.io/thingino-architecture/architecture-signal.html) and [Explorer](https://small6oy.github.io/thingino-architecture/architecture-explorer.html) layouts).

```sh
python3 build.py --open        # check the data, build the pages, open the main one
```

Python 3.11+, standard library only. The pages are generated, so they aren't in git.

- `architecture.toml`: all the content (versions, lanes, parts, connections, boot and journey steps, repos, hand-checked camera facts)
- `import_cameras.py` → `cameras.json`: every Thingino camera config, read from a thingino-firmware checkout
- `build.py`: validates every camera × version view and writes the pages
- `core.js`, `template*.html`: the shared data logic and one template per layout

The full guide is [architecture.md](architecture.md).
