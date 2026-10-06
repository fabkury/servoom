/* servoom community pages: the artist network built from public likes. Reads the JSON
   and the map binary published by the servoom-stats graph job (../stats/data/community/,
   pulled at build time). Text comes from ../stats/i18n.js plus ./i18n.js. */
(() => {
  const LOCALES = ['en', 'es', 'zh', 'ja', 'ru'];
  const KEY = 'servoom-locale';
  let locale = 'en';
  try { const s = localStorage.getItem(KEY); if (LOCALES.includes(s)) locale = s; } catch { /* private mode */ }
  const asked = new URLSearchParams(location.search).get('lang');
  if (LOCALES.includes(asked)) { locale = asked; try { localStorage.setItem(KEY, asked); } catch { /* ignore */ } }
  const LI = LOCALES.indexOf(locale);
  const NUM = { en: 'en-US', es: 'es', zh: 'zh-CN', ja: 'ja', ru: 'ru' }[locale];
  const L = (k) => { const e = window.I18N[k]; return e ? (e[LI] ?? e[0]) : k; };
  const has = (k) => Boolean(window.I18N[k]);
  let regionNames = null;
  try { regionNames = new Intl.DisplayNames([NUM], { type: 'region' }); } catch { /* old browser */ }
  const region = (cc) => cc === 'other' ? L('other') : (() => { try { return regionNames?.of(cc) || cc; } catch { return cc; } })();

  const $ = (tag, attrs = {}, ...kids) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) { if (k === 'html') el.innerHTML = v; else if (v != null) el.setAttribute(k, v); }
    for (const kid of kids.flat()) if (kid != null) el.append(kid);
    return el;
  };
  const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const fmt = (n, d = 0) => (n == null || Number.isNaN(n)) ? '–' : Number(n).toLocaleString(NUM, { maximumFractionDigits: d });
  const compact = (n) => (n == null) ? '–' : Number(n).toLocaleString(NUM, { notation: 'compact', maximumFractionDigits: 1 });
  const pct = (x, d = 0) => (x == null || Number.isNaN(x)) ? '–' : (x * 100).toLocaleString(NUM, { maximumFractionDigits: d }) + '%';
  const timeFmt = new Intl.DateTimeFormat(NUM, { dateStyle: 'medium', timeStyle: 'short' });
  const DATA = '../stats/data/';
  const J = async (p) => { try { const r = await fetch(DATA + p, { cache: 'no-cache' }); return r.ok ? await r.json() : null; } catch { return null; } };
  const main = document.querySelector('main');
  const page = document.body.dataset.page;
  const hashId = () => Number(location.hash.slice(1)) || null;

  // ---- chrome ---------------------------------------------------------------
  const PAGES = ['index', 'communities', 'flows', 'artists', 'history', 'methods'];
  function chrome(status) {
    document.documentElement.lang = locale;
    document.title = `servoom · ${L('land_cm_t')} · ${L('p_' + (page === 'artist' ? 'artists' : page === 'community' ? 'communities' : page))}`;
    const pick = $('select', { id: 'lang', 'aria-label': L('language') },
      LOCALES.map((l, i) => { const o = $('option', { value: l }, ['English', 'Español', '中文', '日本語', 'Русский'][i]); if (l === locale) o.selected = true; return o; }));
    pick.addEventListener('change', () => { try { localStorage.setItem(KEY, pick.value); } catch { /* ignore */ } location.replace(location.pathname + location.hash); });
    const head = $('header', { class: 'top' },
      $('a', { class: 'brand', href: '../' }, 'servoom'),
      $('nav', { class: 'pillars' }, $('a', { href: '../download/' }, L('n_download')), $('a', { href: '../stats/' }, L('n_stats')), $('a', { href: './', class: 'on' }, L('n_community'))),
      pick);
    const cur = page === 'artist' ? 'artists' : page === 'community' ? 'communities' : page;
    const sub = $('nav', { class: 'sub', 'aria-label': L('n_community') },
      PAGES.map((p) => $('a', { href: p === 'index' ? './' : p + '.html', class: p === cur ? 'on' : null }, L('p_' + p))));
    document.body.prepend(head, sub);
    document.body.append($('footer', {}, $('p', {}, L('unofficial')),
      status ? $('p', {}, `${L('updated')} ${timeFmt.format(new Date(status.generated))}`) : null,
      $('p', {}, $('a', { href: 'methods.html' }, L('p_methods')), ' · ', $('a', { href: 'https://github.com/fabkury/servoom' }, 'GitHub'))));
  }
  function sec(key, o = {}) {
    const s = $('section', {}, $('h2', {}, o.title ?? L(key)), has(key + '_n') ? $('p', { class: 'note' }, L(key + '_n')) : null);
    (o.into || main).append(s);
    return s;
  }
  const wait = (s, k = 'collecting') => { s.append($('div', { class: 'wait' }, L(k))); };
  function tiles(list, into = main) {
    into.append($('div', { class: 'tiles' }, list.filter(Boolean).map(([k, v, sub]) =>
      $('div', { class: 'tile' }, $('span', { class: 'v' }, v), $('span', { class: 'l' }, has(k) ? L(k) : k), sub ? $('span', { class: 's' }, sub) : null))));
  }
  function table(s, cols, rows, o = {}) {
    if (!rows || !rows.length) return wait(s);
    s.append($('div', { class: 'scroll' }, $('table', {}, $('thead', {}, $('tr', {}, cols.map(([, lab]) => $('th', {}, has(lab) ? L(lab) : lab)))),
      $('tbody', {}, rows.slice(0, o.max || 300).map((r) => $('tr', {}, cols.map(([k, , f]) => {
        const v = typeof k === 'function' ? k(r) : r[k];
        return $('td', {}, v instanceof Node ? v : (f ? f(v) : (v ?? '–')));
      })))))));
  }
  function draw(s, marks, o = {}) {
    const fig = $('div', { class: 'fig' });
    s.append(fig);
    const width = Math.max(320, Math.min(fig.clientWidth || 860, 900));
    fig.append(window.Plot.plot({
      width, height: o.h || 250, marginLeft: o.ml || 48, marginBottom: o.mb || 30, marginRight: o.mr || 12,
      style: { background: 'transparent', color: cssv('--muted'), fontSize: '11px', fontFamily: 'inherit', overflow: 'visible' },
      x: { label: null, ...(o.x || {}) }, y: { label: null, grid: true, tickFormat: o.yfmt || ((d) => compact(d)), ...(o.y || {}) },
      color: o.color, marks,
    }));
  }
  const avatar = (id, ok) => ok ? $('img', { class: 'av', src: `${DATA}daily/artists/${id}.webp`, alt: '', width: 32, height: 32, loading: 'lazy' }) : $('span', { class: 'av none' });

  // ---- communities: colours and labels --------------------------------------
  const PAL = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#7a5fd1', '#1fa3b5', '#9a7b2f', '#c0392b', '#2e8b57',
    '#e67e22', '#8e44ad', '#16a085', '#d35400', '#2980b9', '#b03a6e', '#6c8e2b', '#a0522d', '#4b77be', '#8c6d1f'];
  const colour = (c, i) => c === 0 ? cssv('--c6') : PAL[(i ?? c) % PAL.length];
  const sizeLab = (sz) => has('size_' + sz) ? L('size_' + sz) : `${sz}×${sz}`;
  const catLab = (c) => has('cat_' + c) ? L('cat_' + c) : c;
  function label(c) {
    if (!c || c.id === 0) return L('small_groups');
    const d = c.descriptor || {};
    const parts = [...(d.cc || []).map(region), ...(d.size || []).map(sizeLab), ...(d.cat || []).map(catLab)];
    return parts.length ? parts.join(' · ') : L('group').replace('{n}', c.id);
  }
  const byId = (comms) => new Map(comms.map((c, i) => [c.id, { ...c, i }]));
  const swatch = (col) => $('i', { class: 'sw', style: `background:${col}` });
  const commLink = (c, i) => $('a', { class: 'cl', href: `community.html#${c.id}` }, swatch(colour(c.id, i)), label(c));

  // ---- map binary -----------------------------------------------------------
  async function loadMap() {
    try {
      const r = await fetch(DATA + 'community/map.bin', { cache: 'no-cache' });
      if (!r.ok) return null;
      const buf = await r.arrayBuffer();
      const dv = new DataView(buf);
      if (String.fromCharCode(...new Uint8Array(buf, 0, 4)) !== 'SVCM') return null;
      const n = dv.getUint32(8, true);
      const x = new Float32Array(n), y = new Float32Array(n), comm = new Uint16Array(n), sc = new Uint8Array(n), id = new Uint32Array(n);
      for (let i = 0, p = 12; i < n; i++, p += 16) {
        x[i] = dv.getFloat32(p, true); y[i] = dv.getFloat32(p + 4, true);
        comm[i] = dv.getUint16(p + 8, true); sc[i] = dv.getUint8(p + 10); id[i] = dv.getUint32(p + 12, true);
      }
      return { n, x, y, comm, sc, id };
    } catch { return null; }
  }

  function mapView(s, m, comms, names, focus) {
    const cm = byId(comms);
    const wrap = $('div', { class: 'mapwrap' });
    const canvas = $('canvas', { class: 'map' });
    const tip = $('div', { class: 'maptip', hidden: '' });
    wrap.append(canvas, tip);
    s.append(wrap);
    const dpr = window.devicePixelRatio || 1;
    let W = 0, H = 0;
    const ctx = canvas.getContext('2d');
    const q = (arr, p) => { const a = Float32Array.from(arr).sort(); return a[Math.floor(p * (a.length - 1))]; };
    const ext = [q(m.x, 0.01), q(m.x, 0.99), q(m.y, 0.01), q(m.y, 0.99)];   // outliers stay reachable by panning
    let base = d3.zoomIdentity;
    const sx = d3.scaleLinear(), sy = d3.scaleLinear();
    let t = d3.zoomIdentity, hot = -1;
    const qt = d3.quadtree().x((i) => m.x[i]).y((i) => m.y[i]).addAll(d3.range(m.n));
    const size = () => {
      W = wrap.clientWidth; H = Math.max(360, Math.min(640, Math.round(W * 0.72)));
      canvas.width = W * dpr; canvas.height = H * dpr; canvas.style.height = H + 'px';
      const pad = 24, span = Math.max(ext[1] - ext[0], ext[3] - ext[2]);
      const k = (Math.min(W, H) - 2 * pad) / span;
      sx.domain([ext[0], ext[0] + span]).range([(W - span * k) / 2, (W + span * k) / 2]);
      sy.domain([ext[2], ext[2] + span]).range([(H + span * k) / 2, (H - span * k) / 2]);
      base = d3.zoomIdentity;
      render();
    };
    const px = (i) => t.applyX(sx(m.x[i])), py = (i) => t.applyY(sy(m.y[i]));
    function render() {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      const r0 = 1.2 * Math.sqrt(t.k);
      ctx.globalAlpha = focus ? 0.25 : 0.8;
      for (let i = 0; i < m.n; i++) {
        const c = m.comm[i];
        if (focus && c === focus) continue;
        ctx.fillStyle = colour(c, cm.get(c)?.i);
        ctx.beginPath(); ctx.arc(px(i), py(i), r0 * (1 + m.sc[i] / 3), 0, 6.28); ctx.fill();
      }
      if (focus) {
        ctx.globalAlpha = 0.95;
        for (let i = 0; i < m.n; i++) {
          if (m.comm[i] !== focus) continue;
          ctx.fillStyle = colour(focus, cm.get(focus)?.i);
          ctx.beginPath(); ctx.arc(px(i), py(i), r0 * (1 + m.sc[i] / 3), 0, 6.28); ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
      if (t.k >= 2.5 || hot >= 0) {
        ctx.font = '11px system-ui, sans-serif'; ctx.fillStyle = cssv('--ink'); ctx.strokeStyle = cssv('--bg'); ctx.lineWidth = 3;
        for (let i = 0; i < m.n; i++) {
          if (!m.id[i] || (t.k < 2.5 && i !== hot) || (t.k < 5 && m.sc[i] < 4 && i !== hot)) continue;
          const nm = names.get(m.id[i]); if (!nm) continue;
          const X = px(i) + 6, Y = py(i) + 4;
          if (X < -40 || X > W + 40 || Y < -10 || Y > H + 10) continue;
          ctx.strokeText(nm, X, Y); ctx.fillText(nm, X, Y);
        }
      }
      if (hot >= 0) {
        ctx.strokeStyle = cssv('--ink'); ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(px(hot), py(hot), r0 * (1 + m.sc[hot] / 3) + 3, 0, 6.28); ctx.stroke();
      }
    }
    const zoom = d3.zoom().scaleExtent([0.7, 40]).on('zoom', (e) => { t = e.transform; render(); });
    d3.select(canvas).call(zoom).on('dblclick.zoom', null);
    canvas.addEventListener('mousemove', (e) => {
      const r = canvas.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      const wx = sx.invert(t.invertX(mx)), wy = sy.invert(t.invertY(my));
      const rad = Math.abs(sx.invert(t.invertX(mx + 8)) - wx);
      const i = qt.find(wx, wy, rad);
      hot = i ?? -1;
      if (hot >= 0) {
        const c = cm.get(m.comm[hot]);
        const nm = m.id[hot] ? names.get(m.id[hot]) : null;
        tip.replaceChildren(nm ? $('b', {}, nm) : $('span', {}, L('anon_artist')), $('br'), swatch(colour(m.comm[hot], c?.i)), label(c || { id: 0 }));
        tip.hidden = false; tip.style.left = Math.min(mx + 14, W - 180) + 'px'; tip.style.top = (my + 14) + 'px';
        canvas.style.cursor = m.id[hot] ? 'pointer' : 'default';
      } else { tip.hidden = true; canvas.style.cursor = 'default'; }
      render();
    });
    canvas.addEventListener('mouseleave', () => { hot = -1; tip.hidden = true; render(); });
    canvas.addEventListener('click', () => { if (hot >= 0 && m.id[hot]) location.href = `artist.html#${m.id[hot]}`; });
    new ResizeObserver(size).observe(wrap);
    size();
    return { setFocus(c) { focus = c; render(); } };
  }

  // ---- chord diagram --------------------------------------------------------
  function chord(s, ids, matrix, labels, colours, o = {}) {
    const fig = $('div', { class: 'fig' });
    s.append(fig);
    const W = Math.max(320, Math.min(fig.clientWidth || 700, 700)), R = W / 2 - 90, r = R - 14;
    const mat = matrix.map((row, i) => row.map((v, j) => (i === j && !o.keepDiag) ? 0 : v));
    const ch = d3.chord().padAngle(0.03).sortSubgroups(d3.descending)(mat);
    const svg = d3.create('svg').attr('viewBox', [-W / 2, -W / 2, W, W]).attr('width', W).attr('height', W).style('max-width', '100%').style('height', 'auto').style('font', '11px system-ui, sans-serif');
    const ink = cssv('--ink');
    const g = svg.append('g').selectAll('g').data(ch.groups).join('g');
    g.append('path').attr('d', d3.arc().innerRadius(r).outerRadius(R)).attr('fill', (d) => colours[d.index]);
    g.append('text').each((d) => { d.angle = (d.startAngle + d.endAngle) / 2; })
      .attr('dy', '0.35em').attr('fill', ink)
      .attr('transform', (d) => `rotate(${(d.angle * 180 / Math.PI - 90)}) translate(${R + 6}) ${d.angle > Math.PI ? 'rotate(180)' : ''}`)
      .attr('text-anchor', (d) => d.angle > Math.PI ? 'end' : null)
      .text((d) => labels[d.index]);
    g.append('title').text((d) => `${labels[d.index]}: ${fmt(d3.sum(mat[d.index]) + d3.sum(mat, (row) => row[d.index]))}`);
    svg.append('g').attr('fill-opacity', 0.6).selectAll('path').data(ch).join('path')
      .attr('d', d3.ribbonArrow ? d3.ribbonArrow().radius(r - 1) : d3.ribbon().radius(r - 1))
      .attr('fill', (d) => colours[d.source.index]).attr('stroke', 'none')
      .append('title').text((d) => `${labels[d.source.index]} → ${labels[d.target.index]}: ${fmt(d.source.value)}`);
    fig.append(svg.node());
  }

  // ---- ego graph ------------------------------------------------------------
  function egoGraph(s, e, cm, names) {
    const fig = $('div', { class: 'fig' });
    s.append(fig);
    const W = Math.max(320, Math.min(fig.clientWidth || 700, 760)), H = 440;
    const nodes = [{ key: 'me', id: e.id, comm: e.comm, me: true, name: names.get(e.id) || '' }];
    const links = [];
    const seen = new Map();
    const add = (x, dir) => {
      const key = x.id ? `id${x.id}` : `${dir}${seen.size}`;
      let n = seen.get(key);
      if (!n) { n = { key, id: x.id, comm: x.comm, name: x.id ? names.get(x.id) : null, give: 0, get: 0 }; seen.set(key, n); nodes.push(n); }
      if (dir === 'to') n.get += x.likes; else n.give += x.likes;
      links.push({ source: dir === 'to' ? 'me' : key, target: dir === 'to' ? key : 'me', v: x.likes });
    };
    e.likes_to.forEach((x) => add(x, 'to'));
    e.likes_from.forEach((x) => add(x, 'from'));
    const svg = d3.create('svg').attr('viewBox', [0, 0, W, H]).attr('width', W).attr('height', H).style('max-width', '100%').style('height', 'auto').style('font', '11px system-ui, sans-serif');
    const sim = d3.forceSimulation(nodes).force('link', d3.forceLink(links).id((d) => d.key).distance((d) => 90 + 60 / Math.sqrt(d.v))).force('charge', d3.forceManyBody().strength(-140)).force('center', d3.forceCenter(W / 2, H / 2)).force('collide', d3.forceCollide(14)).stop();
    for (let i = 0; i < 200; i++) sim.tick();
    svg.append('g').attr('stroke', cssv('--axis')).attr('stroke-opacity', 0.7).selectAll('line').data(links).join('line')
      .attr('x1', (d) => d.source.x).attr('y1', (d) => d.source.y).attr('x2', (d) => d.target.x).attr('y2', (d) => d.target.y).attr('stroke-width', (d) => Math.min(6, 0.8 + Math.log1p(d.v)));
    const g = svg.append('g').selectAll('g').data(nodes).join('g').attr('transform', (d) => `translate(${Math.max(8, Math.min(W - 8, d.x))},${Math.max(8, Math.min(H - 8, d.y))})`);
    g.append('circle').attr('r', (d) => d.me ? 10 : 5 + Math.min(6, Math.log1p((d.give || 0) + (d.get || 0)))).attr('fill', (d) => colour(d.comm, cm.get(d.comm)?.i)).attr('stroke', (d) => d.me ? cssv('--ink') : 'none').attr('stroke-width', 2);
    g.append('title').text((d) => `${d.name || L('anon_artist')} · ${label(cm.get(d.comm) || { id: 0 })}${d.me ? '' : `\n${L('given')}: ${d.get || 0} · ${L('received')}: ${d.give || 0}`}`);
    g.filter((d) => d.name).append('a').attr('href', (d) => d.me ? null : `artist.html#${d.id}`).append('text').attr('dx', 9).attr('dy', 4).attr('fill', cssv('--ink')).attr('stroke', cssv('--surface')).attr('stroke-width', 3).attr('paint-order', 'stroke').text((d) => d.name);
    fig.append(svg.node());
  }

  // ---- shared pieces --------------------------------------------------------
  function mixTable(s, c, whole) {
    const row = (kind, lab) => {
      const keys = [...new Set([...Object.keys(c.mix[kind]), ...Object.keys(whole[kind])])].sort((a, b) => (c.mix[kind][b] || 0) - (c.mix[kind][a] || 0)).slice(0, 8);
      const name = kind === 'cc' ? region : kind === 'size' ? sizeLab : catLab;
      const t = sec(lab, { into: s });
      table(t, [['k', lab, (v) => name(v)], ['a', 'this_community', (v) => pct(v)], ['b', 'whole', (v) => pct(v)]],
        keys.map((k) => ({ k, a: c.mix[kind][k] || 0, b: whole[kind][k] || 0 })));
    };
    row('cc', 'mix_cc'); row('size', 'mix_size'); row('cat', 'mix_cat');
  }
  function hoursChart(s, c, wholeHours) {
    const P = window.Plot;
    const rows = c.hours.flatMap((v, h) => [{ h, v, s: L('this_community') }, { h, v: wholeHours[h], s: L('whole') }]);
    draw(s, [P.ruleY([0], { stroke: cssv('--axis') }), P.lineY(rows, { x: 'h', y: 'v', stroke: 's', strokeWidth: 2, curve: 'monotone-x' }),
      P.tip(rows, P.pointerX({ x: 'h', y: 'v', title: (d) => `${d.s}\n${String(d.h).padStart(2, '0')}:00 UTC · ${pct(d.v, 1)}` }))],
      { h: 200, color: { domain: [L('this_community'), L('whole')], range: [cssv('--c1'), cssv('--c6')] }, x: { domain: [0, 23], tickFormat: (d) => String(d).padStart(2, '0') }, yfmt: (d) => pct(d) });
    s.append($('div', { class: 'legend' }, [[L('this_community'), '--c1'], [L('whole'), '--c6']].map(([lab, col]) => $('span', {}, $('i', { style: `background:var(${col})` }), lab))));
  }
  function communityCard(c, i, status) {
    const card = $('a', { class: 'ccard', href: `community.html#${c.id}` },
      $('h3', {}, swatch(colour(c.id, i)), label(c)),
      $('p', { class: 'cnums' }, `${fmt(c.members)} ${L('members').toLowerCase()} · ${fmt(c.top_artists)} ${L('featured').toLowerCase()} · ${L('internal_share').toLowerCase()} ${pct(c.internal_share)}`));
    return card;
  }

  // ---- pages ----------------------------------------------------------------
  const pages = {
    async index() {
      const [st, cj, ai] = await Promise.all(['community/status.json', 'community/communities.json', 'community/artists/index.json'].map(J));
      chrome(st);
      main.append($('h1', {}, L('land_cm_t')), $('p', { class: 'lede' }, L('p_index_n')));
      if (!st || !cj) return wait(main, 'no_data');
      tiles([['t_artists', fmt(st.artists)], ['t_edges', fmt(st.edges)], ['t_mutual', fmt(st.mutual_pairs)], ['t_communities', fmt(st.communities)],
        ['t_likes_12m', compact(st.artist_likes_in_window)], st.stability != null ? ['t_stability', pct(st.stability)] : null]);
      const m = await loadMap();
      const names = new Map((ai?.artists || []).map((a) => [a.id, a.name]));
      const s = $('section', { class: 'maps' });
      main.append(s);
      if (!m) return wait(s, 'no_data');
      const comms = cj.communities;
      const view = mapView(s, m, comms, names, null);
      const list = $('div', { class: 'clist' }, $('button', { class: 'cbtn on', type: 'button' }, L('all_communities')),
        comms.map((c, i) => $('button', { class: 'cbtn', type: 'button', 'data-id': c.id }, swatch(colour(c.id, i)), $('span', {}, label(c)), $('small', {}, fmt(c.members)))),
        $('button', { class: 'cbtn', type: 'button', 'data-id': 0 }, swatch(colour(0)), $('span', {}, L('small_groups')), $('small', {}, fmt(st.small_groups_artists))));
      list.addEventListener('click', (e) => {
        const b = e.target.closest('button'); if (!b) return;
        list.querySelectorAll('.cbtn').forEach((x) => x.classList.toggle('on', x === b));
        view.setFocus(b.dataset.id == null ? null : Number(b.dataset.id) || (b.dataset.id === '0' ? 0 : null));
      });
      s.append(list);
      const want = /^#c(\d+)$/.exec(location.hash);
      if (want) { const b = list.querySelector(`[data-id="${want[1]}"]`); if (b) b.click(); }
    },

    async communities() {
      const [st, cj] = await Promise.all(['community/status.json', 'community/communities.json'].map(J));
      chrome(st);
      main.append($('h1', {}, L('p_communities')), $('p', { class: 'lede' }, L('p_communities_n')));
      if (!cj) return wait(main, 'no_data');
      main.append($('div', { class: 'cgrid' }, cj.communities.map((c, i) => communityCard(c, i, st))));
      const s = sec('small_groups');
      s.append($('p', { class: 'prose' }, `${fmt(st?.small_groups_artists)} ${L('members').toLowerCase()}`));
    },

    async community() {
      const [st, cj, fj, ai] = await Promise.all(['community/status.json', 'community/communities.json', 'community/flows.json', 'community/artists/index.json'].map(J));
      chrome(st);
      const id = hashId();
      const cm = cj ? byId(cj.communities) : new Map();
      const c = cm.get(id);
      if (!c) { main.append($('h1', {}, L('p_communities'))); return wait(main, 'no_data'); }
      main.append($('h1', {}, swatch(colour(c.id, c.i)), label(c)), $('p', { class: 'lede' }, $('a', { href: `./#c${c.id}` }, L('open_map'))));
      tiles([['members', fmt(c.members)], ['featured', fmt(c.top_artists)], ['uploads_12m', fmt(c.uploads)], ['internal_share', pct(c.internal_share), L('internal_share_n')],
        ['aud_likers', fmt(c.audience.likers), L('audience_n')], ['peak_hour', `${String(c.peak_hour_utc).padStart(2, '0')}:00`]]);
      if (c.top_ids.length) {
        const s = sec('featured');
        const names = new Map((ai?.artists || []).map((a) => [a.id, a]));
        s.append($('div', { class: 'who-grid' }, c.top_ids.map((u) => { const a = names.get(u); return $('a', { class: 'who', href: `artist.html#${u}` }, avatar(u, true), $('span', {}, a?.name || String(u))); })));
      }
      const mx = $('div', { class: 'three' }); main.append(mx);
      mixTable(mx, c, cj.whole);
      const hs = sec('hours'); hoursChart(hs, c, cj.hours);
      if (fj) {
        const ids = fj.communities.ids, k = ids.indexOf(c.id);
        if (k >= 0) {
          const M = fj.communities.likes;
          const rows = (get) => ids.map((o, j) => ({ id: o, v: get(j) })).filter((r) => r.id !== c.id && r.v > 0).sort((a, b) => b.v - a.v).slice(0, 10);
          const tot = (arr) => arr.reduce((a, b) => a + b, 0);
          const given = rows((j) => M[k][j]), gtot = tot(M[k]);
          const recv = rows((j) => M[j][k]), rtot = tot(M.map((row) => row[k]));
          const col = (r) => commLink(cm.get(r.id), cm.get(r.id)?.i);
          const s1 = sec('likes_to_comm'); table(s1, [[col, 'community'], ['v', 'likes', (v) => fmt(v)], [(r) => pct(r.v / gtot, 1), 'share']], given);
          const s2 = sec('likes_from_comm'); table(s2, [[col, 'community'], ['v', 'likes', (v) => fmt(v)], [(r) => pct(r.v / rtot, 1), 'share']], recv);
        }
      }
      const au = sec('audience');
      tiles([['aud_likers', fmt(c.audience.likers)], ['likes', fmt(c.audience.likes)], ['aud_repeat', pct(c.audience.repeat_share)], ['aud_multi', pct(c.audience.multi_member_share)]], au);
    },

    async flows() {
      const [st, cj, fj] = await Promise.all(['community/status.json', 'community/communities.json', 'community/flows.json'].map(J));
      chrome(st);
      main.append($('h1', {}, L('p_flows')), $('p', { class: 'lede' }, L('p_flows_n')));
      if (!cj || !fj) return wait(main, 'no_data');
      const cm = byId(cj.communities);
      const s1 = sec('s_comm_flows');
      const ids = fj.communities.ids.slice(0, 12);
      const M = ids.map((a) => ids.map((b) => fj.communities.likes[fj.communities.ids.indexOf(a)][fj.communities.ids.indexOf(b)]));
      chord(s1, ids, M, ids.map((i) => label(cm.get(i))), ids.map((i) => colour(i, cm.get(i)?.i)));
      s1.append($('div', { class: 'legend' }, ids.map((i) => commLink(cm.get(i), cm.get(i)?.i))));
      const s2 = sec('s_cc_flows');
      const cc = fj.countries;
      const top = cc.ids.slice(0, 16);
      const C = top.map((a) => top.map((b) => cc.likes[cc.ids.indexOf(a)][cc.ids.indexOf(b)]));
      chord(s2, top, C, top.map(region), top.map((_, i) => PAL[i % PAL.length]));
      const s3 = sec('s_cc_matrix');
      const rows = cc.ids.map((a, i) => { const tot = cc.likes[i].reduce((x, y) => x + y, 0); const same = cc.likes[i][i];
        const best = cc.ids.map((b, j) => [b, cc.likes[i][j]]).filter(([b]) => b !== a).sort((x, y) => y[1] - x[1]).slice(0, 3);
        return { cc: a, tot, same: tot ? same / tot : null, best: best.map(([b, v]) => `${region(b)} ${pct(v / tot)}`).join(', ') }; }).filter((r) => r.tot > 0);
      table(s3, [['cc', 'from', region], ['tot', 'likes', (v) => fmt(v)], ['same', 'same_country', (v) => pct(v)], ['best', 'to']], rows);
    },

    async artists() {
      const [st, cj, ai] = await Promise.all(['community/status.json', 'community/communities.json', 'community/artists/index.json'].map(J));
      chrome(st);
      main.append($('h1', {}, L('p_artists')), $('p', { class: 'lede' }, L('p_artists_n')));
      if (!ai || !cj) return wait(main, 'no_data');
      const cm = byId(cj.communities);
      const s = sec('s_artists_list');
      const who = (a) => $('a', { class: 'who', href: `artist.html#${a.id}` }, avatar(a.id, true), $('span', {}, a.name || String(a.id)));
      table(s, [[who, 'artist'], [(a) => commLink(cm.get(a.comm) || { id: 0 }, cm.get(a.comm)?.i), 'community'], ['in', 'in_degree', (v) => fmt(v)], ['out', 'out_degree', (v) => fmt(v)], ['mutual', 'mutual', (v) => fmt(v)]],
        [...ai.artists].sort((a, b) => b.in - a.in), { max: 600 });
    },

    async artist() {
      const id = hashId();
      const [st, cj, ai, e] = await Promise.all(['community/status.json', 'community/communities.json', 'community/artists/index.json', id ? `community/artists/${id}.json` : null].map((p) => p ? J(p) : null));
      chrome(st);
      if (!e || !cj) { main.append($('h1', {}, L('p_artists')), $('p', { class: 'prose' }, L('artist_missing'))); return; }
      const cm = byId(cj.communities);
      const names = new Map((ai?.artists || []).map((a) => [a.id, a.name]));
      const c = cm.get(e.comm) || { id: 0 };
      main.append($('div', { class: 'profile' }, avatar(e.id, true), $('div', {}, $('h1', {}, names.get(e.id) || String(e.id)),
        $('p', { class: 'lede' }, commLink(c, c.i), ' · ', $('a', { href: `../stats/artist.html#${e.id}` }, L('stats_page'))))));
      tiles([['out_degree', fmt(e.out_degree)], ['in_degree', fmt(e.in_degree)], ['mutual', fmt(e.mutual)], ['likes_given', fmt(e.likes_given)], ['likes_received', fmt(e.likes_received)], ['aud_likers', fmt(e.audience.likers), L('audience_n')]]);
      const s = sec('s_ego');
      if (e.likes_to.length + e.likes_from.length) egoGraph(s, e, cm, names); else wait(s);
      const who = (x) => x.id ? $('a', { class: 'who', href: `artist.html#${x.id}` }, avatar(x.id, true), $('span', {}, names.get(x.id) || String(x.id))) : $('span', { class: 'who' }, $('span', { class: 'av none' }), $('span', {}, L('anon_artist')));
      const cols = [[who, 'artist'], [(x) => commLink(cm.get(x.comm) || { id: 0 }, cm.get(x.comm)?.i), 'community'], ['likes', 'likes', (v) => fmt(v)]];
      const two = $('div', { class: 'two' });
      main.append(two);
      const a = sec('likes_to', { into: two }); table(a, cols, e.likes_to);
      const b = sec('likes_from', { into: two }); table(b, cols, e.likes_from);
      const sm = sec('s_a_months');
      const P = window.Plot;
      const rows = e.months.flatMap((r) => [{ x: new Date(r.month + '-01T00:00:00Z'), y: r.given, s: L('given') }, { x: new Date(r.month + '-01T00:00:00Z'), y: r.received, s: L('received') }]);
      if (rows.length) {
        draw(sm, [P.ruleY([0], { stroke: cssv('--axis') }), P.lineY(rows, { x: 'x', y: 'y', stroke: 's', strokeWidth: 2 }), P.tip(rows, P.pointerX({ x: 'x', y: 'y', title: (d) => `${d.s}: ${fmt(d.y)}` }))],
          { color: { domain: [L('given'), L('received')], range: [cssv('--c1'), cssv('--c2')] }, x: { type: 'utc' } });
        sm.append($('div', { class: 'legend' }, [[L('given'), '--c1'], [L('received'), '--c2']].map(([lab, col]) => $('span', {}, $('i', { style: `background:var(${col})` }), lab))));
      } else wait(sm);
      const sc = sec('s_a_likers_comm');
      const lc = Object.entries(e.comm_of_likers).map(([k, v]) => ({ id: Number(k), v })).sort((x, y) => y.v - x.v).slice(0, 10);
      const tot = lc.reduce((x, r) => x + r.v, 0);
      table(sc, [[(r) => commLink(cm.get(r.id) || { id: 0 }, cm.get(r.id)?.i), 'community'], ['v', 'in_degree', (v) => fmt(v)], [(r) => pct(r.v / tot, 1), 'share']], lc);
    },

    async history() {
      const [st, hj] = await Promise.all(['community/status.json', 'community/history.json'].map(J));
      chrome(st);
      main.append($('h1', {}, L('p_history')), $('p', { class: 'lede' }, L('p_history_n')));
      if (!hj || !hj.months?.length) return wait(main, 'no_data');
      const P = window.Plot;
      const rows = hj.months.map((r) => ({ ...r, x: new Date(r.month + '-01T00:00:00Z') }));
      const last = rows.at(-1)?.x;
      const line = (s, k, lab, col, o = {}) => {
        const dat = rows.map((r) => ({ x: r.x, y: r[k], s: L(lab) }));
        draw(s, [P.ruleY([0], { stroke: cssv('--axis') }), P.lineY(dat.filter((d) => +d.x !== +last), { x: 'x', y: 'y', stroke: cssv(col), strokeWidth: 2 }),
          P.lineY(dat.slice(-2), { x: 'x', y: 'y', stroke: cssv(col), strokeWidth: 2, strokeDasharray: '4,4' }),
          P.tip(dat, P.pointerX({ x: 'x', y: 'y', title: (d) => `${d.s}: ${o.pct ? pct(d.y, 1) : fmt(d.y)}` }))], { x: { type: 'utc' }, yfmt: o.pct ? (d) => pct(d) : undefined, h: 220 });
      };
      line(sec('s_h_likes'), 'likes', 'likes', '--c1');
      line(sec('s_h_artists'), 'artists', 't_artists', '--c3');
      const s3 = sec('s_h_shares');
      const dat = rows.flatMap((r) => [{ x: r.x, y: r.mutual_share, s: L('mutual_share') }, { x: r.x, y: r.internal_share, s: L('inside_share') }]);
      draw(s3, [P.ruleY([0], { stroke: cssv('--axis') }), P.lineY(dat, { x: 'x', y: 'y', stroke: 's', strokeWidth: 2 }), P.tip(dat, P.pointerX({ x: 'x', y: 'y', title: (d) => `${d.s}: ${pct(d.y, 1)}` }))],
        { color: { domain: [L('mutual_share'), L('inside_share')], range: [cssv('--c2'), cssv('--c4')] }, x: { type: 'utc' }, yfmt: (d) => pct(d), y: { domain: [0, 1] } });
      s3.append($('div', { class: 'legend' }, [[L('mutual_share'), '--c2'], [L('inside_share'), '--c4']].map(([lab, col]) => $('span', {}, $('i', { style: `background:var(${col})` }), lab))));
      const s4 = sec('s_h_new');
      const nd = rows.flatMap((r) => [{ x: r.x, y: r.newcomers, s: L('newcomers') }, { x: r.x, y: r.newcomers_liked, s: L('newcomers_liked') }]);
      draw(s4, [P.ruleY([0], { stroke: cssv('--axis') }), P.lineY(nd, { x: 'x', y: 'y', stroke: 's', strokeWidth: 2 }), P.tip(nd, P.pointerX({ x: 'x', y: 'y', title: (d) => `${d.s}: ${fmt(d.y)}` }))],
        { color: { domain: [L('newcomers'), L('newcomers_liked')], range: [cssv('--c6'), cssv('--c5')] }, x: { type: 'utc' } });
      s4.append($('div', { class: 'legend' }, [[L('newcomers'), '--c6'], [L('newcomers_liked'), '--c5']].map(([lab, col]) => $('span', {}, $('i', { style: `background:var(${col})` }), lab))));
      main.append($('p', { class: 'note' }, L('approx_note')));
      const t = sec('p_history');
      table(t, [['month', 'date'], ['likes', 'likes', (v) => fmt(v)], ['artists', 't_artists', (v) => fmt(v)], ['mutual_share', 'mutual_share', (v) => pct(v, 1)], ['internal_share', 'inside_share', (v) => pct(v, 1)], ['newcomers', 'newcomers', (v) => fmt(v)], ['newcomers_liked', 'newcomers_liked', (v) => fmt(v)]], [...rows].reverse());
    },

    async methods() {
      const [st, cfg] = await Promise.all(['community/status.json', 'community/config.json'].map(J));
      chrome(st);
      main.append($('h1', {}, L('p_methods')));
      for (const k of ['m_graph', 'm_comm', 'm_map', 'm_auto', 'm_names', 'm_data']) {
        const s = sec(k + '_t'); s.append($('p', { class: 'prose' }, L(k)));
      }
      if (st) {
        const s = sec('m_status');
        table(s, [['k', 'item'], ['v', 'value']], [
          { k: L('t_artists'), v: fmt(st.artists) }, { k: L('t_edges'), v: fmt(st.edges) }, { k: L('t_communities'), v: fmt(st.communities) },
          { k: L('st_uploaders'), v: fmt(st.uploaders_in_window) }, { k: L('st_human_likes'), v: fmt(st.human_likes_in_window) },
          { k: L('st_resolution'), v: String(cfg?.resolution ?? st.resolution) }, { k: L('st_modularity'), v: fmt(st.modularity, 3) },
          { k: L('t_stability'), v: pct(st.stability) }, { k: L('st_seconds'), v: `${fmt(st.seconds)} s` }]);
      }
    },
  };

  (pages[page] || pages.index)().catch((err) => { console.error(err); main.append($('div', { class: 'wait' }, L('page_error'))); });
  window.addEventListener('hashchange', () => { if (page === 'artist' || page === 'community') location.reload(); });
})();
