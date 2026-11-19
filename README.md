# Thingino architecture diagram

An interactive, data-driven diagram of how a [Thingino](https://thingino.com/) camera works: hardware, kernel drivers, libimp and raptor-hal, the streamer daemons, shared-memory rings, consumers, network and outputs. You pick a camera and a firmware version, and the diagram, boot order and upstream repo pins follow.

```sh
python3 build.py --open        # check the data, build the pages, open the main one
```

Python 3.11+, standard library only. The pages are generated, so they aren't in git.

- `architecture.toml`: all the content (cameras, versions, lanes, parts, connections, boot and journey steps, repos)
- `build.py`: validates every camera × version view and writes the pages
- `core.js`, `template*.html`: the shared data logic and one template per layout

The full guide is [architecture.md](architecture.md).
