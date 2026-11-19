// core.js: shared data logic for every layout template. build.py adds it to each page.
// It turns DATA (from architecture.toml) into a "view" for one camera + firmware version,
// using the same rules build.py validates: versions / cameras / needs, variants, placeholders.
const TC = (() => {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  // tiny markup: `code` **bold** *em* [text](url)
  const md = s => esc(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  const plain = s => String(s ?? '').replace(/`([^`]+)`/g, '$1').replace(/\*\*?([^*]+)\*\*?/g, '$1').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');

  const fill = (s, cam, ver) => String(s).replace(/\{(camera|version)\.([A-Za-z0-9_-]+)\}/g, (m, a, k) => {
    const v = (a === 'camera' ? cam : ver)[k];
    return v == null ? m : (Array.isArray(v) ? v.join(', ') : String(v));
  });
  const deepFill = (o, cam, ver) => typeof o === 'string' ? fill(o, cam, ver)
    : Array.isArray(o) ? o.map(x => deepFill(x, cam, ver))
    : (o && typeof o === 'object') ? Object.fromEntries(Object.entries(o).map(([k, v]) => [k, deepFill(v, cam, ver)])) : o;
  const visible = (it, cam, ver) => (!it.versions || it.versions.includes(ver.id))
    && (!it.cameras || it.cameras.includes(cam.id))
    && (!it.needs || it.needs.every(f => (cam.features || []).includes(f)));
  const resolve = (it, cam, ver) => {
    const o = { ...it }; delete o.variant;
    for (const k of [ver.id, cam.id]) if (it.variant && it.variant[k]) Object.assign(o, it.variant[k]);
    return deepFill(o, cam, ver);
  };
  const supports = (c, v) => !c.supports || c.supports.includes(v.id);

  /** Everything a layout needs for one camera + version. */
  function view(D, cam, ver) {
    const vis = it => visible(it, cam, ver), res = it => resolve(it, cam, ver);
    const page = res(D.page);
    let lanes = D.lanes.filter(vis).map(res).map(l => ({ ...l, height: l.height || 76, shape: l.shape || 'box' }));
    const laneById = Object.fromEntries(lanes.map(l => [l.id, l]));
    const nodes = D.nodes.filter(n => laneById[n.lane] && vis(n)).map(res).map(n => {
      const L = laneById[n.lane];
      return { ...n, starts: n.starts ?? L.default_starts, upstream: n.upstream ?? L.default_upstream ?? [], note: n.note ?? L.note };
    });
    lanes = lanes.filter(L => nodes.some(n => n.lane === L.id));
    const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
    const edges = D.edges.filter(e => vis(e) && byId[e.from] && byId[e.to]).map(res);
    const repos = D.repos.filter(vis).map(r => ({ ...res(r), pin: (r.pins && r.pins[ver.id]) || (r.pin ? fill(r.pin, cam, ver) : '') }));
    const repoById = Object.fromEntries(repos.map(r => [r.id, r]));
    const journey = (D.journey || []).filter(vis).map(res);
    const boot = (D.boot || []).filter(vis).map(res);
    const laneIndex = Object.fromEntries(lanes.map((l, i) => [l.id, i]));
    const ins = id => edges.filter(e => e.to === id), outs = id => edges.filter(e => e.from === id);
    return { D, cam, ver, page, lanes, laneById: Object.fromEntries(lanes.map(l => [l.id, l])), laneIndex,
             nodes, byId, edges, repos, repoById, journey, boot, ins, outs,
             fill: s => fill(s, cam, ver), md, esc, plain };
  }

  /** Camera + version from location.hash ("#<camera>+<version>"), falling back to the first supported pair. */
  function pick(D, cid, vid) {
    const cam = D.cameras.find(c => c.id === cid) || D.cameras[0];
    let ver = D.versions.find(v => v.id === vid) || D.versions[0];
    if (!supports(cam, ver)) ver = D.versions.find(v => supports(cam, v)) || D.versions[0];
    return { cam, ver };
  }
  const fromHash = D => { const [c, v] = location.hash.slice(1).split('+'); return pick(D, c, v); };
  const toHash = (cam, ver) => { try { history.replaceState(null, '', '#' + cam.id + '+' + ver.id); } catch (e) { /* ignore */ } };

  /** All nodes reachable upstream and downstream of id (for "trace the whole path"). */
  function trace(V, id) {
    const seen = new Set([id]), walk = (start, dir) => {
      const stack = [start];
      while (stack.length) {
        const cur = stack.pop();
        for (const e of V.edges) {
          const nxt = dir === 'down' ? (e.from === cur ? e.to : null) : (e.to === cur ? e.from : null);
          if (nxt && !seen.has(nxt) && e.kind !== 'control') { seen.add(nxt); stack.push(nxt); }
        }
      }
    };
    walk(id, 'down'); walk(id, 'up');
    return seen;
  }

  // Theme colours for canvas/SVG drawing, read from CSS custom properties.
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const onTheme = fn => {
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', fn);
    new MutationObserver(fn).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  };

  return { esc, md, plain, fill, visible, resolve, supports, view, pick, fromHash, toHash, trace, css, onTheme };
})();
