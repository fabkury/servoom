/* servoom statistics pages. Each page is a function that reads the JSON published by
   the servoom-stats pipeline (stats/data/, pulled at build time) and draws sections.
   Text comes from i18n.js; the language choice is shared with the download tool. */
(() => {
  const LOCALES = ['en', 'es', 'zh', 'ja', 'ru'];
  const KEY = 'servoom-locale';
  let locale = 'en';
  try { const s = localStorage.getItem(KEY); if (LOCALES.includes(s)) locale = s; } catch { /* private mode */ }
  const asked = new URLSearchParams(location.search).get('lang');        // a link can carry ?lang=ja
  if (LOCALES.includes(asked)) { locale = asked; try { localStorage.setItem(KEY, asked); } catch { /* ignore */ } }
  const LI = LOCALES.indexOf(locale);
  const NUM = { en: 'en-US', es: 'es', zh: 'zh-CN', ja: 'ja', ru: 'ru' }[locale];
  const L = (k) => { const e = window.I18N[k]; return e ? (e[LI] ?? e[0]) : k; };
  const has = (k) => Boolean(window.I18N[k]);

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
  const dateFmt = new Intl.DateTimeFormat(NUM, { dateStyle: 'medium', timeZone: 'UTC' });
  const timeFmt = new Intl.DateTimeFormat(NUM, { dateStyle: 'medium', timeStyle: 'short' });
  const J = async (p) => { try { const r = await fetch('data/' + p, { cache: 'no-cache' }); return r.ok ? await r.json() : null; } catch { return null; } };
  const sum = (a, k) => a.reduce((s, r) => s + (r[k] || 0), 0);
  const C = ['--c1', '--c2', '--c3', '--c4', '--c5', '--c6'];
  const SIZE_ORDER = ['16', '32', '64', '128', '256'];

  const main = document.querySelector('main');
  const page = document.body.dataset.page;

  // ---- chrome ---------------------------------------------------------------
  const PAGES = ['index', 'rhythm', 'artwork', 'curation', 'sizes', 'artists', 'audience', 'topics', 'formats', 'popular', 'studies', 'history', 'methods'];
  function chrome(status) {
    document.documentElement.lang = locale;
    document.title = `servoom · ${L('p_' + (page === 'artist' ? 'artists' : page))}`;
    const pick = $('select', { id: 'lang', 'aria-label': L('language') },
      LOCALES.map((l, i) => { const o = $('option', { value: l }, ['English', 'Español', '中文', '日本語', 'Русский'][i]); if (l === locale) o.selected = true; return o; }));
    pick.addEventListener('change', () => { try { localStorage.setItem(KEY, pick.value); } catch { /* ignore */ } location.replace(location.pathname + location.hash); });
    const head = $('header', { class: 'top' },
      $('a', { class: 'brand', href: '../' }, 'servoom'),
      $('nav', { class: 'pillars' }, $('a', { href: '../download/' }, L('n_download')), $('a', { href: './', class: 'on' }, L('n_stats')), $('a', { href: '../artists/' }, L('n_artists'))),
      pick);
    const sub = $('nav', { class: 'sub', 'aria-label': L('n_stats') },
      PAGES.map((p) => $('a', { href: p === 'index' ? './' : p + '.html', class: (p === page || (page === 'artist' && p === 'artists')) ? 'on' : null }, L('p_' + p))));
    document.body.prepend(head, sub);
    const foot = $('footer', {}, $('p', {}, L('unofficial')),
      status ? $('p', {}, `${L('updated')} ${timeFmt.format(new Date(status.generated))}`) : null,
      $('p', {}, $('a', { href: 'methods.html' }, L('p_methods')), ' · ', $('a', { href: 'https://github.com/fabkury/servoom' }, 'GitHub')));
    document.body.append(foot);
  }

  // ---- building blocks ------------------------------------------------------
  function sec(key, asof) {
    const s = $('section', {}, $('h2', {}, L(key)), has(key + '_n') ? $('p', { class: 'note' }, L(key + '_n')) : null);
    if (asof) s.append($('p', { class: 'asof' }, `${L('asof')} ${timeFmt.format(new Date(asof))}`));
    main.append(s);
    return s;
  }
  const wait = (s, k = 'collecting') => { s.append($('div', { class: 'wait' }, L(k))); };
  function tiles(list) {
    main.append($('div', { class: 'tiles' }, list.filter(Boolean).map(([k, v, sub]) =>
      $('div', { class: 'tile' }, $('span', { class: 'v' }, v), $('span', { class: 'l' }, L(k)), sub ? $('span', { class: 's' }, sub) : null))));
  }
  function legend(s, series) {
    if (series.length < 2) return;
    s.append($('div', { class: 'legend' }, series.map(([, lab, c]) => $('span', {}, $('i', { style: `background:var(${c})` }), has(lab) ? L(lab) : lab))));
  }
  const X = (v, kind) => kind === 'unix' ? new Date(v * 1000) : kind === 'day' ? new Date(v + 'T00:00:00Z') : kind === 'month' ? new Date(v + '-01T00:00:00Z') : v;
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
  /** Line or stacked-area chart. series: [[field, labelKey, cssVar], ...] */
  function lines(s, rows, xk, series, o = {}) {
    if (!rows || rows.length < (o.min || 2)) return wait(s);
    const P = window.Plot;
    const lab = (k) => has(k) ? L(k) : k;
    const long = rows.flatMap((r) => series.map(([k, l]) => ({ x: X(r[xk], o.time), y: r[k], s: lab(l), avg: r.avg }))).filter((d) => d.y != null && !Number.isNaN(d.y));
    if (!long.length) return wait(s);
    // o.partial: the last x is a period still in progress, so its segment is drawn dashed
    const xs = o.partial ? [...new Set(long.map((d) => +d.x))].sort((a, b) => a - b) : [];
    const lastX = xs.at(-1), prevX = xs.at(-2) ?? lastX;
    legend(s, series);
    const color = { domain: series.map(([, l]) => lab(l)), range: series.map(([, , c]) => cssv(c)) };
    const tipx = (d) => o.time ? (o.time === 'unix' ? timeFmt : dateFmt).format(d.x) : String(d.x);
    const yf = o.pct ? (v) => pct(v, 1) : (v) => fmt(v, v < 10 ? 2 : 0);
    const marks = [P.ruleY([0], { stroke: cssv('--axis') })];
    if (o.shade) marks.unshift(P.rect([o.shade], { x1: (d) => d[0], x2: (d) => d[1], fill: cssv('--muted'), fillOpacity: 0.13 }));
    if (o.stack) marks.push(P.areaY(long, { x: 'x', y: 'y', fill: 's', fillOpacity: 0.85, curve: 'step-after' }));
    else {
      marks.push(P.lineY(o.partial ? long.filter((d) => +d.x !== lastX) : long, { x: 'x', y: 'y', stroke: 's', strokeWidth: 2, curve: o.curve || 'linear' }));
      if (o.partial) marks.push(P.lineY(long.filter((d) => +d.x >= prevX), { x: 'x', y: 'y', stroke: 's', strokeWidth: 2, strokeDasharray: '4,4' }));
    }
    for (const e of (o.events || [])) marks.push(P.ruleX([X(e.date, 'day')], { stroke: cssv('--muted'), strokeDasharray: '2,3', title: `${e.kind}: ${e.label}` }));
    marks.push(P.tip(long, P.pointerX({ x: 'x', y: 'y', title: (d) => `${d.s}: ${yf(d.y)}\n${tipx(d)}${o.partial && +d.x === lastX ? `\n${L(o.partial)}` : ''}${d.avg > 1 ? `\n${L(o.time === 'unix' ? 'avg_hours' : 'avg_days').replace('{n}', d.avg)}` : ''}`, fill: cssv('--surface'), stroke: cssv('--line') })));
    draw(s, marks, { ...o, color, x: { type: o.time ? 'utc' : (o.xtype || undefined), ...(o.x || {}) }, yfmt: o.pct ? (d) => pct(d) : undefined });
  }
  /** Horizontal bars. rows: [{label, value, ...}] */
  function bars(s, rows, o = {}) {
    if (!rows || !rows.length) return wait(s);
    const P = window.Plot;
    const yf = o.pct ? (v) => pct(v, 1) : (v) => fmt(v, 1);
    draw(s, [
      P.barX(rows, { y: 'label', x: 'value', fill: cssv(o.c || '--c1'), sort: o.keep ? null : { y: '-x' }, insetTop: 3, insetBottom: 3, title: (d) => `${d.label}: ${yf(d.value)}` }),
      P.text(rows, { y: 'label', x: 'value', text: (d) => yf(d.value), dx: 6, textAnchor: 'start', fill: cssv('--ink2') }),
      P.ruleX([0], { stroke: cssv('--axis') }),
    ], { h: 26 * rows.length + 40, ml: o.ml || 110, mr: 56, x: { grid: true, label: null, tickFormat: o.pct ? (d) => pct(d) : (d) => compact(d) }, y: { label: null, grid: false, tickFormat: (d) => d, domain: o.keep ? rows.map((r) => r.label) : undefined } });
  }
  /** Hour-by-weekday heatmap in the viewer's chosen UTC offset. rows: [{dow, hod, v}] */
  function heat(s, rows, o = {}) {
    if (!rows || rows.length < 24) return wait(s);
    const P = window.Plot;
    const off = Number(document.getElementById('tz')?.value || 0);
    const days = L('weekdays').split(',');
    const data = rows.map((r) => { let h = r.hod + off, d = r.dow; if (h < 0) { h += 24; d = (d + 6) % 7; } if (h > 23) { h -= 24; d = (d + 1) % 7; } return { h, d: days[d], v: r.v }; });
    draw(s, [P.cell(data, { x: 'h', y: 'd', fill: 'v', inset: 1, title: (d) => `${d.d} ${String(d.h).padStart(2, '0')}:00 · ${fmt(d.v, 1)}` })],
      { h: 230, ml: 44, x: { type: 'band', domain: [...Array(24).keys()], label: null }, y: { domain: days, label: null, grid: false, tickFormat: (d) => d },
        color: { type: 'linear', range: [cssv('--heat0'), cssv('--c1')] } });
  }
  function table(s, cols, rows, o = {}) {
    if (!rows || !rows.length) return wait(s);
    const t = $('table', {}, $('thead', {}, $('tr', {}, cols.map(([, lab]) => $('th', {}, has(lab) ? L(lab) : lab)))),
      $('tbody', {}, rows.slice(0, o.max || 200).map((r) => $('tr', {}, cols.map(([k, , f]) => {
        const v = typeof k === 'function' ? k(r) : r[k];
        return $('td', {}, v instanceof Node ? v : (f ? f(v) : (v ?? '–')));
      })))));
    s.append($('div', { class: 'scroll' }, t));
  }
  const text = (s, k) => s.append($('p', { class: 'prose' }, L(k)));
  /** Monthly rows with every month from the first one to `end` present; months without a row count zero. */
  const fillMonths = (rows, end, fields) => {
    if (!rows?.length) return rows;
    const by = new Map(rows.map((r) => [r.m, r])), out = [];
    let [y, m] = rows[0].m.split('-').map(Number);
    for (let k = rows[0].m; k <= end; k = `${y}-${String(m).padStart(2, '0')}`) {
      out.push(by.get(k) || { m: k, ...Object.fromEntries(fields.map((f) => [f, 0])) });
      if (++m > 12) { m = 1; y++; }
    }
    return out;
  };
  /** A reading taken after missed runs covers several periods (hours for 'unix' rows, days for
      'day' rows). It is replaced by that many equal rows, one per period, so the chart stays
      continuous and the totals stay true. span(r) = periods the row covers; such rows get `avg`. */
  const spread = (rows, xk, kind, fields, span) => {
    if (!rows?.length) return rows;
    const at = (v) => kind === 'unix' ? v / 3600 : Date.parse(v + 'T00:00:00Z') / 864e5;
    const back = (v, j) => kind === 'unix' ? v - 3600 * j : new Date(Date.parse(v + 'T00:00:00Z') - 864e5 * j).toISOString().slice(0, 10);
    const out = [];
    rows.forEach((r, i) => {
      const gap = i ? Math.round(at(r[xk]) - at(rows[i - 1][xk])) : 1;       // never spread over periods that have their own row
      const k = Math.max(1, Math.min(gap, Math.round(span(r) || 1)));
      for (let j = k - 1; j >= 0; j--) out.push(k === 1 ? r : { ...r, [xk]: back(r[xk], j), ...Object.fromEntries(fields.map((f) => [f, r[f] == null ? r[f] : r[f] / k])), avg: k });
    });
    return out;
  };
  const bySize = (rows, field, xk) => {            // pivot long [{m,size,field}] into wide rows keyed by xk
    const m = new Map();
    for (const r of rows) { if (!m.has(r[xk])) m.set(r[xk], { [xk]: r[xk] }); m.get(r[xk])[r.size] = r[field]; }
    return [...m.values()].sort((a, b) => String(a[xk]).localeCompare(String(b[xk])));
  };
  const sizeSeries = SIZE_ORDER.map((sname, i) => [sname, `${sname}×${sname}`, C[i]]);
  const avatar = (a) => a.avatar ? $('img', { class: 'av', src: `data/daily/artists/${a.id}.webp`, alt: '', width: 32, height: 32, loading: 'lazy' }) : $('span', { class: 'av none' });
  const daily7 = (hourly, k) => { const last = hourly.slice(-168); const hrs = sum(last, 'hours') || last.length; return hrs ? sum(last, k) / hrs * 24 : null; };

  // ---- pages ----------------------------------------------------------------
  const pages = {
    async index() {
      const [st, hourly, daily, ua, su, cal, dst] = await Promise.all(['pulse/status.json', 'pulse/hourly.json', 'daily/daily.json', 'pulse/uploads_all.json', 'pulse/signups.json', 'daily/calendar.json', 'daily/status.json'].map(J));
      const ev = cal?.events || [];
      const lastOf = (a) => (a && a.length) ? a[a.length - 1] : null;
      const up7 = daily?.uploads ? sum(daily.uploads.slice(-8, -1), 'n') / 7 : null;
      const sg = su?.series?.slice(-42) || [];
      tiles([
        ['t_uploads', fmt(up7), L('t_per_day')],
        hourly?.length > 12 ? ['t_people', fmt(daily7(hourly, 'people')), L('t_per_day_30')] : null,
        hourly?.length > 12 ? ['t_likes', fmt(daily7(hourly, 'likes')), L('t_per_day_30')] : null,
        hourly?.length > 12 ? ['t_views', fmt(daily7(hourly, 'views')), L('t_per_day_30')] : null,
        sg.length ? ['t_signups', fmt(sum(sg, 'per_day') / sg.length), L('t_per_day')] : null,
        lastOf(daily?.uploaders) ? ['t_uploaders', fmt(lastOf(daily.uploaders)['30']), L('t_30d')] : null,
        daily?.likers?.length >= 7 ? ['t_likers', fmt(lastOf(daily.likers)['30']), L('t_30d')] : null,   // needs a week of like events first
        daily?.catalog ? ['t_catalog', compact(daily.catalog.n), `${compact(daily.catalog.likes)} ${L('likes').toLowerCase()}`] : null,
      ]);
      const hrs = spread(hourly, 't', 'unix', ['people', 'auto', 'views'], (r) => r.hours);
      const flows = spread(daily?.flows, 'day', 'day', ['people', 'auto', 'unattributed'], (r) => r.hours / 24);
      let s = sec('s_hourly_likes', st?.last_pulse);
      lines(s, hrs, 't', [['people', 'people', '--c1'], ['auto', 'automated', '--c2']], { time: 'unix', stack: true, min: 3 });
      s = sec('s_hourly_views');
      lines(s, hrs, 't', [['views', 'views', '--c3']], { time: 'unix', min: 3 });
      s = sec('s_daily_flows', dst?.snapshot);
      lines(s, flows, 'day', [['people', 'people', '--c1'], ['auto', 'automated', '--c2'], ['unattributed', 'unattributed', '--c6']], { time: 'day', stack: true, events: ev });
      s = sec('s_uploads_day');
      lines(s, daily?.uploads?.slice(0, -1), 'day', [['n', 'uploads', '--c1']], { time: 'day', events: ev });
      s = sec('s_uploads_all', st?.generated);
      lines(s, ua?.days?.slice(1), 'day', [['public', 'k_public', '--c1'], ['private', 'k_private', '--c5'], ['held', 'k_held', '--c4'], ['removed', 'k_removed', '--c2']], { time: 'day', stack: true });
      s = sec('s_signups');
      lines(s, su?.series, 't', [['per_day', 'signups_day', '--c3']], { time: 'unix', events: ev });
      s = sec('s_status');
      table(s, [['k', 'item'], ['v', 'value']], [
        { k: L('st_pulse'), v: st ? timeFmt.format(new Date(st.last_pulse)) : '–' },
        { k: L('st_snapshot'), v: dst ? timeFmt.format(new Date(dst.snapshot)) : '–' },
        { k: L('st_mode'), v: st ? L(st.mode === 'normal' ? 'mode_normal' : 'mode_degraded') : '–' },
        { k: L('st_window'), v: st ? fmt(st.artworks_in_window) : '–' },
        { k: L('st_catalog'), v: dst ? fmt(dst.artworks) : '–' },
      ]);
    },

    async rhythm() {
      const [h, hu, promo] = await Promise.all(['pulse/heat.json', 'pulse/heat_uploads.json', 'pulse/promo.json'].map(J));
      const tz = $('select', { id: 'tz' }, [...Array(27).keys()].map((i) => { const o = i - 12; const el = $('option', { value: o }, `UTC${o >= 0 ? '+' : ''}${o}`); if (o === Math.round(-new Date().getTimezoneOffset() / 60)) el.selected = true; return el; }));
      main.append($('p', { class: 'control' }, $('label', { for: 'tz' }, L('timezone') + ' '), tz));
      const holder = $('div');
      main.append(holder);
      const render = () => {
        holder.replaceChildren();
        const keep = main; // sections append to main; move them into holder
        const mk = (k, rows) => { const s = sec(k); holder.append(s); heat(s, rows); };
        mk('s_heat_likes', h?.map((r) => ({ dow: r.dow, hod: r.hod, v: r.likes })));
        mk('s_heat_views', h?.map((r) => ({ dow: r.dow, hod: r.hod, v: r.views })));
        mk('s_heat_uploads', hu?.map((r) => ({ dow: r.dow, hod: r.hod, v: r.uploads })));
        mk('s_heat_promo', promo?.heat?.filter((r) => r.kind === 'rec').map((r) => ({ dow: r.dow, hod: r.hod, v: r.n })));
        void keep;
      };
      tz.addEventListener('change', render);
      render();
    },

    async artwork() {
      const [curves, daily, surv, ua] = await Promise.all(['pulse/curves.json', 'daily/daily.json', 'daily/survival.json', 'pulse/uploads_all.json'].map(J));
      const hours = (rows) => rows.filter((r) => r.b < 168).map((r) => ({ ...r, age: r.b / 24 }));
      const wide = (by, field) => { const m = new Map(); for (const r of hours((curves || []).filter((c) => c.by === by && c.n >= 30))) { if (!m.has(r.age)) m.set(r.age, { age: r.age }); m.get(r.age)[r.key] = r[field]; } return [...m.values()].sort((a, b) => a.age - b.age); };
      let s = sec('s_curve_tier');
      lines(s, wide('tier', 'people'), 'age', [['rec', 'tier_rec', '--c2'], ['new', 'tier_new', '--c1'], ['none', 'tier_none', '--c6']], { xtype: 'linear', min: 6, x: { label: L('age_days') } });
      s = sec('s_curve_views');
      lines(s, wide('tier', 'views'), 'age', [['rec', 'tier_rec', '--c2'], ['new', 'tier_new', '--c1'], ['none', 'tier_none', '--c6']], { xtype: 'linear', min: 6, x: { label: L('age_days') } });
      s = sec('s_curve_size');
      lines(s, wide('size', 'people'), 'age', sizeSeries, { xtype: 'linear', min: 6, x: { label: L('age_days') } });
      s = sec('s_long');
      const days = (curves || []).filter((c) => c.by === 'all' && c.b >= 168 && c.n >= 30).map((r) => ({ age: r.b - 168 + 7, people: r.people * 24, views: r.views * 24 }));
      lines(s, days, 'age', [['people', 'people', '--c1']], { xtype: 'linear', min: 4, x: { label: L('age_days') } });
      s = sec('s_backcat');
      const ba = daily?.by_age; const cat = daily?.catalog_by_age;
      if (ba?.length) { const last = ba.filter((r) => r.day === ba[ba.length - 1].day);
        table(s, [['age', 'age'], [(r) => cat?.[r.age], 'artworks', fmt], ['dl', 'likes', fmt], ['dlp', 'people', fmt], ['dla', 'automated', fmt], ['dv', 'views', fmt]], last); } else wait(s);
      s = sec('s_survival');
      table(s, [['days', 'after_days'], ['n', 'artworks', fmt], ['gone', 'gone', (v) => pct(v, 1)], ['removed', 'k_removed', (v) => pct(v, 1)], ['made private', 'k_private', (v) => pct(v, 1)], ['hidden', 'k_hidden', (v) => pct(v, 1)]], surv?.by_age);
      s = sec('s_review');
      const rv = ua?.review;
      if (rv?.resolved >= 5) table(s, [['k', 'item'], ['v', 'value']], [{ k: L('rv_resolved'), v: fmt(rv.resolved) }, { k: L('rv_approved'), v: pct(rv.approved_share) }, { k: L('rv_wait'), v: fmt(rv.median_wait_h, 1) }]); else wait(s);
    },

    async curation() {
      const [promo, cur] = await Promise.all(['pulse/promo.json', 'daily/curation.json'].map(J));
      let s = sec('s_promo_day');
      const pd = new Map(); for (const r of (promo?.per_day || [])) { if (!pd.has(r.day)) pd.set(r.day, { day: r.day }); pd.get(r.day)[r.kind] = r.n; }
      lines(s, [...pd.values()], 'day', [['rec', 'tier_rec', '--c2'], ['new', 'tier_new', '--c1']], { time: 'day' });
      s = sec('s_odds');
      lines(s, bySize((cur?.by_month || []).filter((r) => r.n >= 30), 'rec', 'm'), 'm', sizeSeries, { time: 'month', pct: true });
      s = sec('s_odds_new');
      lines(s, bySize((cur?.by_month || []).filter((r) => r.n >= 30), 'new', 'm'), 'm', sizeSeries, { time: 'month', pct: true });
      s = sec('s_odds_cat');
      table(s, [['category', 'category'], ['n', 'uploads', fmt], ['new', 'reach_new', (v) => pct(v)], ['rec', 'reach_rec', (v) => pct(v)]], cur?.by_category?.sort((a, b) => b.n - a.n));
      s = sec('s_delay');
      table(s, [[(r) => L(r.kind === 'rec' ? 'tier_rec' : 'tier_new'), 'tier'], ['count', 'n', fmt], ['25%', 'q25', (v) => fmt(v, 1)], ['50%', 'median', (v) => fmt(v, 1)], ['75%', 'q75', (v) => fmt(v, 1)], ['90%', 'q90', (v) => fmt(v, 1)]], promo?.delay?.filter((r) => r.count >= 5));
      s = sec('s_effect');
      const after = (promo?.after || []).filter((r) => r.n >= 10 && r.rel < 72);
      if (promo?.before && after.length > 6) s.append($('p', { class: 'note' }, `${L('before_rate')}: ${fmt(promo.before.likes_per_hour, 2)} ${L('likes_h')}, ${fmt(promo.before.views_per_hour, 1)} ${L('views_h')} (n=${fmt(promo.before.n)})`));
      lines(s, after, 'rel', [['people', 'people', '--c1'], ['likes', 'raw_likes', '--c6']], { xtype: 'linear', min: 6, x: { label: L('hours_after') } });
      s = sec('s_refiled');
      lines(s, spread(cur?.per_day, 'day', 'day', ['refiled'], (r) => r.days), 'day', [['refiled', 'refiled', '--c4']], { time: 'day' });
    },

    async sizes() {
      const [ps, sz] = await Promise.all(['pulse/sizes.json', 'daily/sizes.json'].map(J));
      let s = sec('s_share');
      const d30 = (ps || []).filter((r) => r.days === 30);
      if (d30.length) {
        const tot = (k) => sum(d30, k) || NaN;
        table(s, [[(r) => `${r.size}×${r.size}`, 'canvas'], [(r) => r.uploads / tot('uploads'), 'uploads', pct], [(r) => r.people / tot('people'), 'people', pct], [(r) => r.likes / tot('likes'), 'raw_likes', pct], [(r) => r.views / tot('views'), 'views', pct]],
          d30.sort((a, b) => SIZE_ORDER.indexOf(a.size) - SIZE_ORDER.indexOf(b.size)));
      } else wait(s);
      s = sec('s_mature');
      table(s, [[(r) => `${r.size}×${r.size}`, 'canvas'], ['n', 'uploads', fmt], ['uploaders', 'uploaders', fmt], ['like_med', 'median_likes', fmt], ['like_p90', 'top10_likes', fmt], ['watch_med', 'median_views', fmt], ['new', 'reach_new', pct], ['rec', 'reach_rec', pct]],
        sz?.mature?.sort((a, b) => SIZE_ORDER.indexOf(a.size) - SIZE_ORDER.indexOf(b.size)));
      const co = (sz?.cohorts || []).filter((r) => r.n >= 30);
      s = sec('s_size_uploads');
      lines(s, bySize(co, 'n', 'm'), 'm', sizeSeries, { time: 'month' });
      s = sec('s_size_likes');
      lines(s, bySize(co, 'like_med', 'm'), 'm', sizeSeries, { time: 'month' });
      s = sec('s_photo');
      lines(s, bySize(co, 'photo', 'm'), 'm', sizeSeries, { time: 'month', pct: true });
      s = sec('s_features');
      const all = new Map(); for (const r of co) { const a = all.get(r.m) || { m: r.m, n: 0, layer: 0, music: 0, ai: 0 }; a.n += r.n; a.layer += r.layer * r.n; a.music += r.music * r.n; a.ai += r.ai * r.n; all.set(r.m, a); }
      lines(s, [...all.values()].sort((a, b) => a.m.localeCompare(b.m)).map((a) => ({ m: a.m, layer: a.layer / a.n, music: a.music / a.n, ai: a.ai / a.n })), 'm',
        [['layer', 'f_layer', '--c1'], ['music', 'f_music', '--c3'], ['ai', 'f_ai', '--c5']], { time: 'month', pct: true });
    },

    async artists() {
      const [idx, lead, ret, cc, score, meth] = await Promise.all(['daily/artists/index.json', 'pulse/leaders.json', 'daily/retention.json', 'daily/countries.json', 'daily/score.json', 'daily/methods.json'].map(J));
      const byId = new Map((idx?.artists || []).map((a) => [a.id, a]));
      const who = (r) => { const a = byId.get(r.id) || r; return $('a', { class: 'who', href: `artist.html#${r.id}` }, avatar({ ...a, id: r.id }), $('span', {}, r.name || a.name)); };
      let s = sec('s_leaders');
      const top = (lead || []).filter((r) => r.days === 7 && r.people > 0).slice(0, 25);
      table(s, [[who, 'artist'], ['uploads', 'uploads', fmt], ['people', 'people', fmt], ['likes', 'raw_likes', fmt], ['views', 'views', fmt]], top.length ? top : null);
      s = sec('s_leaders30');
      const top30 = (lead || []).filter((r) => r.days === 30 && r.people > 0).slice(0, 25);
      table(s, [[who, 'artist'], ['uploads', 'uploads', fmt], ['people', 'people', fmt], ['likes', 'raw_likes', fmt], ['views', 'views', fmt]], top30.length ? top30 : null);
      s = sec('s_top_artists', idx?.generated);
      table(s, [[who, 'artist'], ['cc', 'country'], ['level', 'level'], ['fans', 'followers', fmt], ['picks', 'picks_12m', fmt], ['uploads', 'uploads_12m', fmt], ['likes', 'likes_12m', fmt], ['views', 'views_12m', fmt]],
        idx?.artists?.slice().sort((a, b) => b.picks - a.picks || b.likes - a.likes), { max: 300 });
      s = sec('s_conc');
      const c1 = meth?.concentration?.top1?.slice(-1)[0]?.[''], c10 = meth?.concentration?.top10?.slice(-1)[0]?.[''];
      if (c1 != null) bars(s, [{ label: L('top1'), value: c1 }, { label: L('top10'), value: c10 }], { pct: true, keep: true, ml: 150 }); else wait(s);
      s = sec('s_retention');
      lines(s, ret?.cohorts?.filter((r) => r.n >= 30).slice(0, -3), 'm', [['again30', 'again30', '--c1'], ['again90', 'again90', '--c3']], { time: 'month', pct: true });
      s = sec('s_new_uploaders');
      lines(s, ret?.cohorts?.slice(0, -1), 'm', [['n', 'new_uploaders', '--c1']], { time: 'month' });
      s = sec('s_countries');
      bars(s, Object.entries(cc?.uploaders_365d || {}).slice(0, 15).map(([k, v]) => ({ label: k, value: v / cc.n })), { pct: true, ml: 60 });
      s = sec('s_score');
      if (score?.ready) { table(s, [['k', 'action'], ['v', 'points', (v) => fmt(v, 2)]], Object.entries(score.points).map(([k, v]) => ({ k, v }))); s.append($('p', { class: 'note' }, `R² ${fmt(score.r2, 2)} · n=${fmt(score.n)}`)); } else wait(s);
    },

    async artist() {
      const id = Number(location.hash.slice(1));
      const [idx, a] = await Promise.all([J('daily/artists/index.json'), J(`daily/artists/${id}.json`)]);
      const me = idx?.artists?.find((x) => x.id === id);
      if (!me) { wait(sec('s_artist_missing'), 'artist_missing'); return; }
      main.append($('div', { class: 'profile' }, avatar(me), $('div', {}, $('h1', {}, me.name), $('p', { class: 'note' }, [me.cc, `${L('level')} ${me.level}`, me.fans != null ? `${fmt(me.fans)} ${L('followers').toLowerCase()}` : null].filter(Boolean).join(' · ')))));
      tiles([['uploads_12m', fmt(me.uploads)], ['picks_12m', fmt(me.picks)], ['likes_12m', fmt(me.likes)], ['views_12m', fmt(me.views)]]);
      // The tiles count the 365 days before the snapshot; the monthly charts go further back and shade that window.
      const now = new Date(idx.generated);
      const months = fillMonths(a?.months, idx.generated.slice(0, 7), ['n', 'picks', 'likes', 'views']);
      const mo = { time: 'month', partial: 'month_partial' };
      if (months?.length > 1) mo.shade = [new Date(Math.max(now - 365 * 864e5, X(months[0].m, 'month'))), X(months.at(-1).m, 'month')];
      const monthly = (key, series) => {
        const s = sec(key);
        lines(s, months, 'm', series, mo);
        if (mo.shade) s.append($('p', { class: 'note' }, L('a_shade_note')));
      };
      monthly('s_a_uploads', [['n', 'uploads', '--c1'], ['picks', 'tier_rec', '--c2']]);
      monthly('s_a_likes', [['likes', 'raw_likes', '--c1']]);
      let s;
      s = sec('s_a_fans');
      lines(s, a?.daily, 'day', [['fans', 'followers', '--c3']], { time: 'day', min: 3 });
      s = sec('s_a_daily');
      lines(s, spread(a?.daily, 'day', 'day', ['dlp_day', 'dl_day'], (r) => r.days), 'day', [['dlp_day', 'people', '--c1'], ['dl_day', 'raw_likes', '--c6']], { time: 'day', min: 3 });
    },

    async audience() {
      const [au, su, fu, cm] = await Promise.all(['daily/audience.json', 'pulse/signups.json', 'daily/funnel.json', 'pulse/comments.json'].map(J));
      let s = sec('s_likers');
      lines(s, au?.likers, 'day', [['1', 'd1', '--c1'], ['7', 'd7', '--c3'], ['30', 'd30', '--c5']], { time: 'day' });
      s = sec('s_likers_new');
      lines(s, spread(au?.new_likers, 'day', 'day', [''], (r) => r.days), 'day', [['', 'new_likers', '--c1']], { time: 'day' });
      s = sec('s_returning');
      lines(s, au?.returning, 'day', [['', 'returning', '--c1']], { time: 'day', pct: true });
      s = sec('s_who_likes');
      const one = (a) => a?.slice(-1)[0]?.[''];
      if (one(au?.uploader_share) != null) bars(s, [{ label: L('likers_are_uploaders'), value: one(au.uploader_share) }, { label: L('likes_from_uploaders'), value: one(au.likes_by_uploaders) }, { label: L('likes_top1'), value: one(au.top1pct) }, one(au.reciprocity) != null ? { label: L('reciprocity'), value: one(au.reciprocity) } : null].filter(Boolean), { pct: true, keep: true, ml: 230 }); else wait(s);
      s = sec('s_per_liker');
      bars(s, au?.likes_per_liker ? Object.entries(au.likes_per_liker).map(([k, v]) => ({ label: k, value: v })) : null, { keep: true, ml: 60 });
      s = sec('s_funnel');
      table(s, [['week', 'signup_week'], ['accounts_est', 'accounts', fmt], ['likers', 'ever_liked', fmt], ['liked_7d', 'liked_7d', fmt], ['uploaded', 'ever_uploaded', fmt], [(r) => r.accounts_est ? r.likers / r.accounts_est : null, 'activation', (v) => pct(v, 1)]],
        fu?.weeks?.filter((r) => r.accounts_est > 0).slice(-16).reverse());
      s = sec('s_signup_cc');
      const cc = su?.countries || {}; const tot = Object.values(cc).reduce((x, y) => x + y, 0);
      bars(s, tot >= 50 ? Object.entries(cc).slice(0, 15).map(([k, v]) => ({ label: k, value: v / tot })) : null, { pct: true, ml: 60 });
      s = sec('s_comments');
      lines(s, cm?.days, 'day', [['people', 'people', '--c1'], ['auto', 'automated', '--c2']], { time: 'day', stack: true });
      s = sec('s_comment_scripts');
      const sc = cm?.scripts || {}; const st = Object.values(sc).reduce((x, y) => x + y, 0);
      bars(s, st >= 30 ? Object.entries(sc).map(([k, v]) => ({ label: L('sc_' + k), value: v / st })) : null, { pct: true, ml: 120 });
    },

    async topics() {
      const [tg, rx, cats, cal] = await Promise.all(['daily/tags.json', 'daily/remix.json', 'pulse/categories.json', 'daily/calendar.json'].map(J));
      const tagCols = [[(r) => '#' + r.tag, 'tag'], ['uploads', 'uploads', fmt], ['uploaders', 'uploaders', fmt], ['likes', 'raw_likes', fmt], ['views', 'views', fmt]];
      let s = sec('s_tags_rising');
      table(s, [[(r) => '#' + r.tag, 'tag'], ['now', 'uploaders_week', fmt], ['before', 'uploaders_before', (v) => fmt(v, 1)], ['gain', 'gain', (v) => fmt(v, 1)]], tg?.rising?.filter((r) => r.gain > 0), { max: 20 });
      s = sec('s_tags_30');
      table(s, tagCols, tg?.top_30d, { max: 30 });
      s = sec('s_remix');
      lines(s, rx?.by_month?.filter((r) => r.n >= 100), 'm', [['remix', 'remix_share', '--c1']], { time: 'month', pct: true });
      s = sec('s_most_remixed');
      table(s, [['artist', 'artist'], ['gid', 'artwork_id'], ['remixes', 'remixes', fmt], ['like', 'raw_likes', fmt]], rx?.most_remixed?.filter((r) => r.remixes >= 2));
      s = sec('s_dedications');
      table(s, [['from', 'from'], ['to', 'to'], ['n', 'uploads', fmt]], rx?.dedications, { max: 30 });
      s = sec('s_scripts');
      const sm = new Map(); for (const r of (rx?.title_scripts || [])) { if (!sm.has(r.m)) sm.set(r.m, { m: r.m, tot: 0 }); const o = sm.get(r.m); o[r.script] = r.n; o.tot += r.n; }
      const ss = [...sm.values()].sort((a, b) => a.m.localeCompare(b.m)).map((o) => ({ m: o.m, latin: (o.latin || 0) / o.tot, han: (o.han || 0) / o.tot, kana: (o.kana || 0) / o.tot, cyrillic: (o.cyrillic || 0) / o.tot, hangul: (o.hangul || 0) / o.tot }));
      lines(s, ss, 'm', [['latin', 'sc_latin', '--c1'], ['han', 'sc_han', '--c2'], ['kana', 'sc_kana', '--c3'], ['cyrillic', 'sc_cyrillic', '--c4'], ['hangul', 'sc_hangul', '--c5']], { time: 'month', pct: true });
      s = sec('s_categories');
      const log = cats?.log || [];
      if (log.length) { const last = log[log.length - 1], first = log[0]; const dd = Math.max(1, (last.t - first.t) / 86400);
        table(s, [[(r) => cats.names[r.k] || r.k, 'category'], ['n', 'artworks', fmt], [(r) => log.length > 1 ? (r.n - (first.n[r.k] ?? r.n)) / dd : null, 'per_day', (v) => fmt(v, 1)]],
          Object.entries(last.n).map(([k, n]) => ({ k, n })).sort((a, b) => b.n - a.n));
        if (last.match) s.append($('p', { class: 'note' }, `${L('contest')}: ${last.match} · ${fmt(last.n['30'])} ${L('entries')}`)); } else wait(s);
      s = sec('s_calendar');
      table(s, [['date', 'date'], ['kind', 'kind'], ['label', 'what']], cal?.events?.slice().reverse(), { max: 40 });
    },

    async formats() {
      const f = await J('daily/formats.json');
      let s = sec('s_anim');
      lines(s, f?.per_day?.map((r) => ({ day: r.day, anim: r.anim / r.n, layer: r.layer / r.n, music: r.music / r.n })), 'day', [['anim', 'animated', '--c1'], ['layer', 'f_layer', '--c3'], ['music', 'f_music', '--c5']], { time: 'day', pct: true, min: 3 });
      s = sec('s_dups');
      lines(s, f?.per_day?.map((r) => ({ day: r.day, other: r.dup_other / r.n, self: r.dup_self / r.n, near: r.near_other / r.n })), 'day', [['other', 'dup_other', '--c2'], ['near', 'dup_near', '--c4'], ['self', 'dup_self', '--c6']], { time: 'day', pct: true, min: 3 });
      s = sec('s_containers');
      table(s, [['fmt', 'container'], [(r) => `${r.size}×${r.size}`, 'canvas'], ['n', 'files', fmt], [(r) => r.anim / r.n, 'animated', pct], [(r) => r.decoded ? r.frames / r.decoded : null, 'avg_frames', (v) => fmt(v, 1)], [(r) => r.decoded ? r.colors / r.decoded : null, 'avg_colors', (v) => fmt(v)], [(r) => r.bytes / r.n / 1024, 'avg_kb', (v) => fmt(v, 1)]],
        f?.by_format?.sort((a, b) => b.n - a.n));
      if (f?.since) s.append($('p', { class: 'note' }, `${L('since')} ${f.since}`));
    },

    async popular() {
      const p = await J('pulse/popular.json');
      const name = (l) => { const [c, sz] = l.split('_'); const cn = { 18: L('tier_rec'), 0: L('tier_new'), 1: 'Default', 3: 'Character', 4: 'Emoji', 6: 'Nature', 8: 'Pattern', 12: 'Photo' }[c] || `#${c}`; return sz === '127' ? `${cn} (${L('all_sizes')})` : `${cn} ${({ 1: 16, 2: 32, 4: 64, 16: 128, 32: 256 })[sz]}px`; };
      let s = sec('s_pop_entry');
      table(s, [[(r) => name(r.lst), 'list'], ['n', 'artworks', fmt], ['likes', 'median_likes', fmt], ['views', 'median_views', fmt], ['age_days', 'median_age_days', (v) => fmt(v, 1)], ['rec_share', 'reach_rec', pct]], p?.entry);
      s = sec('s_pop_dwell');
      table(s, [[(r) => name(r.lst), 'list'], ['count', 'n', fmt], ['50%', 'median_hours', (v) => fmt(v, 1)], ['90%', 'q90_hours', (v) => fmt(v, 1)]], p?.dwell?.filter((r) => r.count >= 10));
      s = sec('s_pop_tiers');
      const tot = sum(p?.tiers || [], 'n');
      bars(s, tot ? p.tiers.map((r) => ({ label: L('tier_' + r.tier), value: r.n / tot })) : null, { pct: true, ml: 130 });
    },

    async studies() {
      const [st, sc] = await Promise.all(['daily/study.json', 'daily/score.json'].map(J));
      let s = sec('s_study');
      if (st?.ready) table(s, [['k', 'item'], ['v', 'value']], [
        { k: L('sd_n'), v: fmt(st.n) }, { k: L('sd_extra'), v: fmt(st.extra_auto_likes, 1) }, { k: L('sd_base'), v: fmt(st.baseline_later_people_likes, 2) },
        { k: L('sd_diff'), v: `${st.difference >= 0 ? '+' : ''}${fmt(st.difference, 2)} (± ${fmt(1.96 * st.se, 2)})` }]);
      else { wait(s, 'study_wait'); if (st) s.append($('p', { class: 'note' }, `n = ${fmt(st.n)}`)); }
      text(s, 'study_caveat');
      s = sec('s_score');
      if (sc?.ready) table(s, [['k', 'action'], ['v', 'points', (v) => fmt(v, 2)]], Object.entries(sc.points).map(([k, v]) => ({ k, v }))); else wait(s);
    },

    async history() {
      const h = await J('daily/history.json');
      if (h?.measured_from) main.append($('p', { class: 'note' }, `${L('hist_intro')} ${h.measured_from}.`));
      let s = sec('s_h_uploads');
      lines(s, bySize(h?.uploads || [], 'n', 'm').slice(0, -1), 'm', sizeSeries, { time: 'month', stack: true });
      s = sec('s_h_signups');
      lines(s, h?.signups?.filter((r) => r.m >= '2018-06').slice(0, -1), 'm', [['accounts', 'accounts', '--c3']], { time: 'month' });
      s = sec('s_h_rec');
      lines(s, h?.rec_picks?.slice(0, -1), 'm', [['n', 'tier_rec', '--c2']], { time: 'month' });
      s = sec('s_h_years');
      table(s, [['y', 'upload_year'], ['n', 'artworks', fmt], ['likes', 'raw_likes', fmt], ['views', 'views', fmt], [(r) => r.likes / r.n, 'likes_per_artwork', (v) => fmt(v, 1)], ['auto_share_oct2026', 'auto_share', (v) => pct(v, 1)]], h?.by_upload_year);
    },

    async methods() {
      const [st, dst, daily, meth] = await Promise.all(['pulse/status.json', 'daily/status.json', 'daily/daily.json', 'daily/methods.json'].map(J));
      let s = sec('s_m_what'); text(s, 'm_what');
      s = sec('s_m_people'); text(s, 'm_people');
      lines(s, spread(daily?.flows, 'day', 'day', ['likes', 'people'], (r) => r.hours / 24), 'day', [['likes', 'raw_likes', '--c6'], ['people', 'people', '--c1']], { time: 'day' });
      table(s, [['r', 'id_range']], (st?.automated_ranges || meth?.ranges || []).map(([lo, hi, par]) => ({ r: `${fmt(lo)} – ${fmt(hi)}${par === 0 ? ' · ' + L('even_ids') : par === 1 ? ' · ' + L('odd_ids') : ''}` })));
      if (meth?.tracked_likes) s.append($('p', { class: 'note' }, `${L('tracked')}: ${fmt(meth.tracked_likes.people)} ${L('people').toLowerCase()}, ${fmt(meth.tracked_likes.automated)} ${L('automated').toLowerCase()}`));
      s = sec('s_m_how'); for (const k of ['m_how1', 'm_how2', 'm_how3']) text(s, k);
      s = sec('s_m_privacy'); for (const k of ['m_priv1', 'm_priv2']) text(s, k);
      s = sec('s_m_limits'); for (const k of ['m_lim1', 'm_lim2', 'm_lim3']) text(s, k);
      s = sec('s_status');
      table(s, [['k', 'item'], ['v', 'value']], [
        { k: L('st_pulse'), v: st ? timeFmt.format(new Date(st.last_pulse)) : '–' }, { k: L('st_snapshot'), v: dst ? timeFmt.format(new Date(dst.snapshot)) : '–' },
        { k: L('st_mode'), v: st ? L(st.mode === 'normal' ? 'mode_normal' : 'mode_degraded') : '–' },
        { k: L('st_warnings'), v: dst?.warnings?.length ? dst.warnings.join(', ') : L('none') }]);
    },
  };

  (async () => {
    const status = await J('pulse/status.json') || await J('daily/status.json');
    chrome(status);
    if (page !== 'artist') main.append($('h1', {}, L('p_' + page)), has('p_' + page + '_n') ? $('p', { class: 'lede' }, L('p_' + page + '_n')) : null);
    if (!status) { main.append($('div', { class: 'wait' }, L('no_data'))); return; }
    try { await pages[page](); } catch (e) { console.error(e); main.append($('div', { class: 'wait' }, L('page_error'))); }
  })();
  window.addEventListener('hashchange', () => { if (page === 'artist') location.reload(); });
})();
