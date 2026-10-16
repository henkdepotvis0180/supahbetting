'use strict';

const liveUi = {league:'all', matches:[], selected:null, current:null, request:0, detailRequest:0};
const liveEl = id => document.getElementById(id);
const liveEscape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function liveGet(url) {
  let response;
  try { response = await fetch(url); }
  catch (_error) { throw Error('Geen verbinding met de lokale SupahBetting-server.'); }
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'Livegegevens konden niet worden opgehaald');
  return data;
}

function liveTime(stamp, fallback) {
  if (stamp) {
    const date = new Date(stamp);
    if (!Number.isNaN(date.getTime())) {
      return new Intl.DateTimeFormat('nl-NL', {
        day:'numeric', month:'short', hour:'2-digit', minute:'2-digit'
      }).format(date);
    }
  }
  return fallback || 'Onbekende tijd';
}

function liveScore(match) {
  return match.score_home === null || match.score_away === null ? '– : –' :
    String(match.score_home) + ' : ' + String(match.score_away);
}

function liveStatus(match) {
  const allowed = ['scheduled','finished','estimated_live','unknown'];
  const status = allowed.includes(match.status) ? match.status : 'unknown';
  return '<span class="live-pill ' + status + '">' +
    liveEscape(match.status_label || 'Onbekende status') + '</span>';
}

function liveDraw() {
  const host = liveEl('live-list');
  if (!liveUi.matches.length) {
    host.innerHTML = '<div class="empty">Geen wedstrijden gevonden voor de actuele speelronde. ' +
      'Probeer een andere competitie of ververs later.</div>';
    return;
  }
  const priority = {estimated_live:0, scheduled:1, unknown:2, finished:3};
  const sorted = [...liveUi.matches].sort((a,b) => {
    const diff = (priority[a.status] ?? 4) - (priority[b.status] ?? 4);
    return diff || (Date.parse(a.kickoff) || 0) - (Date.parse(b.kickoff) || 0);
  });
  host.innerHTML = sorted.map(m => {
    return '<button class="live-game" type="button" data-live-id="' + Number(m.id) +
      '" data-live-league="' + liveEscape(m.league) + '" aria-label="Bekijk wedstrijd ' +
      liveEscape(m.home_team) + ' tegen ' + liveEscape(m.away_team) + '">' +
      '<div class="live-game-top"><span class="live-game-league">' + liveEscape(m.league_name) +
      '</span><span>' + liveEscape(m.round || liveTime(m.kickoff,m.kickoff_source_local)) + '</span></div>' +
      '<div class="live-game-teams"><div class="live-game-names"><strong>' + liveEscape(m.home_team) +
      '</strong><strong>' + liveEscape(m.away_team) + '</strong></div>' +
      '<span class="live-game-score">' + liveScore(m) + '</span></div>' +
      '<div class="live-game-bottom">' + liveStatus(m) +
      '<span class="live-action">Bekijk feed →</span></div></button>';
  }).join('');
}

function liveWarnings(warnings, fetched) {
  const warn = liveEl('live-warning');
  if (warnings.length) {
    warn.textContent = '⚠ ' + warnings.join(' · ');
    warn.classList.remove('hidden');
  } else {
    warn.textContent = '';
    warn.classList.add('hidden');
  }
  liveEl('live-updated').textContent = fetched ?
    'Bron laatst opgehaald: ' + liveTime(fetched) + ' · verversing elke 90 seconden' :
    'Nog geen livegegevens opgehaald';
}

async function liveReload(showLoading=false) {
  if (document.visibilityState === 'hidden') return;
  const request = ++liveUi.request;
  if (showLoading) liveEl('live-list').innerHTML = '<div class="empty">Wedstrijden laden…</div>';
  try {
    const result = await liveGet('/api/live/matches?league=' + encodeURIComponent(liveUi.league));
    if (request !== liveUi.request) return;
    liveUi.matches = result.matches;
    liveWarnings(result.warnings || (result.warning ? [result.warning] : []), result.fetched_at);
    liveDraw();
  } catch (error) {
    if (request !== liveUi.request) return;
    liveWarnings([error.message], null);
    if (!liveUi.matches.length) liveEl('live-list').innerHTML =
      '<div class="empty">De openbare livebron is momenteel niet bereikbaar. ' +
      'De handmatige wedstrijdanalyse blijft wel werken.</div>';
  }
}

function liveEvents(detail) {
  if (!Array.isArray(detail.timeline) || !detail.timeline.length) {
    return '<div class="slip-empty">Geen doelpuntengebeurtenissen gemeld. ' +
      'Dit is geen volledige livecommentaarfeed.</div>';
  }
  return '<ol class="live-timeline">' + detail.timeline.map(event => {
    const minute = event.minute === null ? '—' : String(event.minute) + "'";
    const hint = event.is_penalty ? 'Penalty' : event.is_own_goal ? 'Eigen doelpunt' : 'Doelpunt';
    const score = event.score_home === null || event.score_away === null ? '' :
      ' · ' + String(event.score_home) + '–' + String(event.score_away);
    return '<li><span class="live-minute">' + liveEscape(minute) + '</span>' +
      '<div class="live-event-description">⚽ ' + liveEscape(event.player) + liveEscape(score) +
      '<small>' + liveEscape(hint) + '</small></div></li>';
  }).join('') + '</ol>';
}

function liveRenderDetail(detail) {
  liveEl('live-detail-title').textContent = detail.league_name + ' · Wedstrijd';
  liveEl('live-detail').innerHTML =
    '<div class="live-detail-scoreboard"><div class="live-detail-team">' + liveEscape(detail.home_team) +
    '</div><div class="live-detail-result">' + liveScore(detail) +
    '</div><div class="live-detail-team">' + liveEscape(detail.away_team) + '</div></div>' +
    '<div class="live-detail-meta">' + liveStatus(detail) + ' · ' +
    liveEscape(liveTime(detail.kickoff,detail.kickoff_source_local)) + '</div>' +
    '<div class="live-detail-meta">Laatste ophalen: ' + liveEscape(liveTime(detail.fetched_at)) + '</div>' +
    (detail.stale ? '<div class="live-warning">⚠ Verouderde gegevens: de bron is tijdelijk niet bereikbaar.</div>' : '') +
    '<h3 class="live-section-title">⚽ Doelpuntenfeed</h3>' + liveEvents(detail) +
    '<div class="live-detail-notice">' + liveEscape(detail.timeline_note) + '</div>' +
    '<h3 class="live-section-title">Openbare uitzending</h3>' +
    '<div class="live-detail-notice">' + liveEscape(detail.video_note) + '</div>' +
    (detail.video_embed_url ? '<div class="live-detail-actions"><button id="live-load-video" class="btn btn-quiet" type="button">▶ Officiële video tonen</button></div>' +
      '<div class="live-video" id="live-video-box"></div>' : '') +
    '<div class="live-detail-actions">' +
    (detail.status === 'scheduled' ? '<button id="live-use-analysis" type="button" class="btn btn-primary">Gebruik wedstrijd voor analyse</button>' : '') +
    '<button id="live-reload-detail" type="button" class="btn btn-quiet">↻ Feed verversen</button></div>' +
    '<div class="live-mini-foot">Data: <a href="https://www.openligadb.de/" target="_blank" rel="noopener noreferrer">OpenLigaDB</a> · ' +
    '<a href="https://www.openligadb.de/lizenz" target="_blank" rel="noopener noreferrer">ODbL 1.0</a>. ' +
    'Communitygegevens kunnen vertraagd zijn. <strong>Geen live bookmakerodds.</strong></div>';
  liveEl('live-reload-detail').addEventListener('click', () => liveLoadDetail(true));
  if (detail.status === 'scheduled') {
    liveEl('live-use-analysis').addEventListener('click', () => liveUseForAnalysis(detail));
  }
  if (detail.video_embed_url) {
    liveEl('live-load-video').addEventListener('click', () => {
      const url = detail.video_embed_url;
      if (!/^https:\/\/www\.youtube-nocookie\.com\/embed\/[A-Za-z0-9_-]{11}$/.test(url)) return;
      const iframe = document.createElement('iframe');
      iframe.src = url;
      iframe.title = 'Door gebruiker geverifieerde officiële openbare video';
      iframe.loading = 'lazy';
      iframe.referrerPolicy = 'strict-origin-when-cross-origin';
      iframe.sandbox = 'allow-scripts allow-same-origin allow-presentation';
      iframe.allow = 'encrypted-media; picture-in-picture; fullscreen';
      iframe.allowFullscreen = true;
      liveEl('live-video-box').replaceChildren(iframe);
      liveEl('live-load-video').disabled = true;
    }, {once:true});
  }
}

async function liveLoadDetail(quiet=false) {
  if (!liveUi.selected || !liveEl('live-dialog').open || document.visibilityState === 'hidden') return;
  const requested = ++liveUi.detailRequest;
  const selected = liveUi.selected;
  if (!quiet) liveEl('live-detail').innerHTML = '<p class="muted">Wedstrijdfeed wordt geladen…</p>';
  try {
    const result = await liveGet('/api/live/matches/' + selected.id + '?league=' + encodeURIComponent(selected.league));
    if (requested !== liveUi.detailRequest || !liveEl('live-dialog').open) return;
    liveUi.current = result;
    liveRenderDetail(result);
  } catch (error) {
    if (requested !== liveUi.detailRequest || !liveEl('live-dialog').open) return;
    if (!quiet || !liveUi.current) {
      liveEl('live-detail').innerHTML = '<p class="live-detail-notice">Wedstrijdfeed niet beschikbaar. ' +
        'Sluit dit venster en probeer later opnieuw.</p>';
    } else {
      const warning = document.createElement('div');
      warning.className = 'live-warning';
      warning.textContent = '⚠ Verversen mislukt: ' + error.message;
      liveEl('live-detail').prepend(warning);
    }
  }
}

function liveOpen(matchId, league) {
  const dialog = liveEl('live-dialog');
  if (dialog.open) return;
  liveUi.selected = {id:matchId,league};
  liveUi.current = null;
  dialog.showModal();
  liveLoadDetail();
}

function liveClose() {
  liveUi.detailRequest++;
  liveUi.selected = null;
  liveUi.current = null;
  if (liveEl('live-dialog').open) liveEl('live-dialog').close();
}

function liveUseForAnalysis(match) {
  const editor = liveEl('match-editor');
  const form = liveEl('match-form');
  editor.open = true;
  form.elements.namedItem('home_team').value = match.home_team;
  form.elements.namedItem('away_team').value = match.away_team;
  form.elements.namedItem('source').value = 'OpenLigaDB (schemapunt; xG en odds handmatig)';
  const date = match.kickoff ? new Date(match.kickoff) : null;
  form.elements.namedItem('kickoff').value = date && !Number.isNaN(date.getTime()) ?
    new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0,16) : '';
  for (const field of ['home_xg','away_xg','odds_home','odds_draw','odds_away']) {
    form.elements.namedItem(field).value = '';
  }
  liveClose();
  editor.scrollIntoView({behavior:'smooth',block:'start'});
  form.elements.namedItem('home_xg').focus({preventScroll:true});
}

function liveInit() {
  liveEl('live-league').addEventListener('change', event => {
    liveUi.league = event.target.value;
    liveUi.matches = [];
    liveReload(true);
  });
  liveEl('live-refresh').addEventListener('click', () => liveReload(true));
  liveEl('live-list').addEventListener('click', event => {
    const button = event.target.closest('button[data-live-id]');
    if (button) liveOpen(Number(button.dataset.liveId), button.dataset.liveLeague);
  });
  liveEl('live-close').addEventListener('click', liveClose);
  liveEl('live-dialog').addEventListener('click', event => {
    if (event.target === liveEl('live-dialog')) liveClose();
  });
  liveEl('live-dialog').addEventListener('close', () => {
    liveUi.detailRequest++;
    liveUi.selected = null;
    liveUi.current = null;
  });
  liveReload(true);
  window.setInterval(() => {
    if (document.visibilityState === 'visible') liveReload();
  }, 90000);
  window.setInterval(() => {
    if (liveEl('live-dialog').open && document.visibilityState === 'visible') liveLoadDetail(true);
  }, 45000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      liveReload();
      if (liveEl('live-dialog').open) liveLoadDetail(true);
    }
  });
}

document.addEventListener('DOMContentLoaded', liveInit);
