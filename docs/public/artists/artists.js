/* servoom artists pages: who likes whose work, from public likes. Reads the JSON
   published by the servoom-stats network job (../stats/data/network/, pulled at build
   time). Text comes from ../stats/i18n.js plus ./i18n.js. */
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
  const region = (cc) => { if (!cc) return ''; try { return regionNames?.of(cc) || cc; } catch { return cc; } };

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
  const PAGES = ['index', 'history', 'methods'];
  function chrome(status) {
    document.documentElement.lang = locale;
    document.title = `servoom · ${L('n_artists')} · ${L('p_' + (page === 'artist' ? 'index' : page))}`;
    const pick = $('select', { id: 'lang', 'aria-label': L('language') },
      LOCALES.map((l, i) => { const o = $('option', { value: l }, ['English', 'Español', '中文', '日本語', 'Русский'][i]); if (l === locale) o.selected = true; return o; }));
    pick.addEventListener('change', () => { try { localStorage.setItem(KEY, pick.value); } catch { /* ignore */ } location.replace(location.pathname + location.hash); });
    const head = $('header', { class: 'top' },
      $('a', { class: 'brand', href: '../' }, 'servoom'),
      $('nav', { class: 'pillars' }, $('a', { href: '../download/' }, L('n_download')), $('a', { href: '../stats/' }, L('n_stats')), $('a', { href: './', class: 'on' }, L('n_artists'))),
      pick);
    const cur = page === 'artist' ? 'index' : page;
    const sub = $('nav', { class: 'sub', 'aria-label': L('n_artists') },
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
    if (!rows || !rows.length) return wait(s, o.empty || 'collecting');
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
  const legend = (s, items) => s.append($('div', { class: 'legend' }, items.map(([lab, col]) => $('span', {}, $('i', { style: `background:var(${col})` }), lab))));
  const avatar = (id, ok = true) => ok ? $('img', { class: 'av', src: `${DATA}daily/artists/${id}.webp`, alt: '', width: 32, height: 32, loading: 'lazy' }) : $('span', { class: 'av none' });
  const who = (id, name) => $('a', { class: 'who', href: `artist.html#${id}` }, avatar(id), $('span', {}, name || String(id)));

  // ---- pages ----------------------------------------------------------------
  const pages = {
    async index() {
      const [st, ai] = await Promise.all(['network/status.json', 'network/artists/index.json'].map(J));
      chrome(st);
      main.append($('h1', {}, L('n_artists')), $('p', { class: 'lede' }, L('p_index_n')));
      if (!st || !ai) return wait(main, 'no_data');
      tiles([['t_artists', fmt(st.artists)], ['t_pairs', fmt(st.pairs)], ['t_mutual', fmt(st.mutual_pairs)], ['t_likes_12m', compact(st.artist_likes_in_window)], ['t_featured', fmt(st.featured_in_network)]]);
      const s = sec('s_list');
      const sortSel = $('select', { id: 'sort', 'aria-label': L('sort_by') },
        [['in', 'in_degree'], ['received', 'likes_received'], ['out', 'out_degree'], ['given', 'likes_given'], ['mutual', 'mutual'], ['audience', 'aud_likers']].map(([k, lab]) => $('option', { value: k }, L(lab))));
      const q = $('input', { type: 'search', id: 'q', placeholder: L('search'), 'aria-label': L('search') });
      s.append($('div', { class: 'control row' }, $('label', { for: 'sort' }, L('sort_by'), ' ', sortSel), q));
      const holder = $('div');
      s.append(holder);
      const render = () => {
        const k = sortSel.value, needle = q.value.trim().toLowerCase();
        const rows = ai.artists.filter((a) => !needle || (a.name || '').toLowerCase().includes(needle) || region(a.cc).toLowerCase().includes(needle)).sort((a, b) => b[k] - a[k]);
        holder.replaceChildren();
        table(holder, [[(a) => who(a.id, a.name), 'artist'], ['cc', 'country', region], ['in', 'in_degree', (v) => fmt(v)], ['received', 'likes_received', (v) => fmt(v)],
          ['out', 'out_degree', (v) => fmt(v)], ['given', 'likes_given', (v) => fmt(v)], ['mutual', 'mutual', (v) => fmt(v)], ['audience', 'aud_likers', (v) => fmt(v)]], rows, { max: 600, empty: 'none' });
      };
      sortSel.addEventListener('change', render); q.addEventListener('input', render);
      render();
    },

    async artist() {
      const id = hashId();
      const [st, ai, e] = await Promise.all(['network/status.json', 'network/artists/index.json', id ? `network/artists/${id}.json` : null].map((p) => p ? J(p) : null));
      chrome(st);
      if (!e) { main.append($('h1', {}, L('n_artists')), $('p', { class: 'prose' }, L('artist_missing')), $('p', {}, $('a', { href: './' }, L('p_index')))); return; }
      const names = new Map((ai?.artists || []).map((a) => [a.id, a.name]));
      main.append($('div', { class: 'profile' }, avatar(e.id), $('div', {}, $('h1', {}, names.get(e.id) || String(e.id)),
        $('p', { class: 'lede' }, region(e.cc), e.cc ? ' · ' : '', $('a', { href: `../stats/artist.html#${e.id}` }, L('stats_page'))))));
      tiles([['in_degree', fmt(e.in_degree)], ['likes_received', fmt(e.likes_received)], ['out_degree', fmt(e.out_degree)], ['likes_given', fmt(e.likes_given)], ['mutual', fmt(e.mutual)], ['aud_likers', fmt(e.audience.likers), L('audience_n')]]);
      const list = (key, side) => {
        const s = sec(key, { into: two });
        const rows = side.named.map((x) => ({ ...x, name: names.get(x.id) }));
        if (side.others.artists) rows.push({ other: true, likes: side.others.likes, n: side.others.artists });
        table(s, [[(x) => x.other ? $('span', { class: 'who' }, $('span', { class: 'av none' }), $('span', {}, L('others_n').replace('{n}', fmt(x.n)))) : who(x.id, x.name), 'artist'],
          [(x) => x.other ? '' : region(x.cc), 'country'], ['likes', 'likes', (v) => fmt(v)]], rows, { empty: 'none' });
      };
      const two = $('div', { class: 'two' });
      main.append(two);
      list('likes_from', e.likes_from);
      list('likes_to', e.likes_to);
      if (e.mutual_named?.length) {
        const s = sec('mutual_named');
        s.append($('div', { class: 'who-grid' }, e.mutual_named.map((u) => who(u, names.get(u)))));
      }
      const sm = sec('s_a_months');
      const P = window.Plot;
      const rows = e.months.flatMap((r) => [{ x: new Date(r.month + '-01T00:00:00Z'), y: r.given, s: L('given') }, { x: new Date(r.month + '-01T00:00:00Z'), y: r.received, s: L('received') }]);
      if (rows.length > 2) {
        draw(sm, [P.ruleY([0], { stroke: cssv('--axis') }), P.lineY(rows, { x: 'x', y: 'y', stroke: 's', strokeWidth: 2 }), P.tip(rows, P.pointerX({ x: 'x', y: 'y', title: (d) => `${d.s}: ${fmt(d.y)}` }))],
          { color: { domain: [L('given'), L('received')], range: [cssv('--c1'), cssv('--c2')] }, x: { type: 'utc' } });
        legend(sm, [[L('given'), '--c1'], [L('received'), '--c2']]);
      } else wait(sm);
    },

    async history() {
      const [st, hj] = await Promise.all(['network/status.json', 'network/history.json'].map(J));
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
          P.tip(dat, P.pointerX({ x: 'x', y: 'y', title: (d) => `${d.s}: ${o.pct ? pct(d.y, 1) : fmt(d.y)}` }))], { x: { type: 'utc' }, yfmt: o.pct ? (d) => pct(d) : undefined, h: 220, y: o.pct ? { domain: [0, Math.max(0.2, ...dat.map((d) => d.y || 0))] } : {} });
      };
      line(sec('s_h_likes'), 'likes', 'likes', '--c1');
      line(sec('s_h_artists'), 'artists', 't_artists', '--c3');
      line(sec('s_h_mutual'), 'mutual_share', 'mutual_share', '--c2', { pct: true });
      const s4 = sec('s_h_new');
      const nd = rows.flatMap((r) => [{ x: r.x, y: r.newcomers, s: L('newcomers') }, { x: r.x, y: r.newcomers_liked, s: L('newcomers_liked') }]);
      draw(s4, [P.ruleY([0], { stroke: cssv('--axis') }), P.lineY(nd, { x: 'x', y: 'y', stroke: 's', strokeWidth: 2 }), P.tip(nd, P.pointerX({ x: 'x', y: 'y', title: (d) => `${d.s}: ${fmt(d.y)}` }))],
        { color: { domain: [L('newcomers'), L('newcomers_liked')], range: [cssv('--c6'), cssv('--c5')] }, x: { type: 'utc' } });
      legend(s4, [[L('newcomers'), '--c6'], [L('newcomers_liked'), '--c5']]);
      main.append($('p', { class: 'note' }, L('approx_note')));
      const t = sec('p_history');
      table(t, [['month', 'date'], ['likes', 'likes', (v) => fmt(v)], ['artists', 't_artists', (v) => fmt(v)], ['pairs', 't_pairs', (v) => fmt(v)], ['mutual_share', 'mutual_share', (v) => pct(v, 1)], ['newcomers', 'newcomers', (v) => fmt(v)], ['newcomers_liked', 'newcomers_liked', (v) => fmt(v)]], [...rows].reverse());
    },

    async methods() {
      const st = await J('network/status.json');
      chrome(st);
      main.append($('h1', {}, L('p_methods')));
      for (const k of ['m_graph', 'm_auto', 'm_names', 'm_data']) {
        const s = sec(k + '_t'); s.append($('p', { class: 'prose' }, L(k)));
      }
      if (st) {
        const s = sec('m_status');
        table(s, [['k', 'item'], ['v', 'value']], [
          { k: L('t_artists'), v: fmt(st.artists) }, { k: L('t_pairs'), v: fmt(st.pairs) }, { k: L('t_mutual'), v: fmt(st.mutual_pairs) },
          { k: L('st_uploaders'), v: fmt(st.uploaders_in_window) }, { k: L('st_human_likes'), v: fmt(st.human_likes_in_window) },
          { k: L('t_likes_12m'), v: fmt(st.artist_likes_in_window) }, { k: L('t_featured'), v: fmt(st.featured_in_network) }, { k: L('st_seconds'), v: `${fmt(st.seconds)} s` }]);
      }
    },
  };

  (pages[page] || pages.index)().catch((err) => { console.error(err); main.append($('div', { class: 'wait' }, L('page_error'))); });
  window.addEventListener('hashchange', () => { if (page === 'artist') location.reload(); });
})();
