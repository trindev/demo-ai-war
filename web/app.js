'use strict';

// ---------- ตัวช่วย ----------
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const hhmm = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const num = (n, d = 0) => Number(n || 0).toLocaleString('th-TH', { maximumFractionDigits: d });
const coordText = (lat, lng) => `${Number(lat).toFixed(5)}, ${Number(lng).toFixed(5)}`;
const mapsUrl = (lat, lng) => `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
const coordLink = (lat, lng) => `<a class="coords" href="${mapsUrl(lat, lng)}" target="_blank" rel="noopener">${coordText(lat, lng)}</a>`;
const timeText = (ts) => new Date(ts * 1000).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' });

const ICONS = {
  camera: '<path d="M4 8h3l1.5-2h7L17 8h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
  trash: '<path d="M5 7h14M9 7V5h6v2M7 7l1 12h8l1-12"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  alert: '<path d="M12 5.5v8.5M12 17.8v.4"/>',
  nav: '<path d="M12 3l7 17-7-4-7 4z"/>',
  qr: '<path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h2v2h-2zM18 18h2v2h-2zM14 18h2v2h-2zM18 14h2v2h-2z"/>',
  spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>',
  bag: '<path d="M7 8h10l1.5 12h-13z"/><path d="M9 8V6a3 3 0 016 0v2"/>',
};
const ic = (name, size = 18) => `<svg class="ic" viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true">${ICONS[name]}</svg>`;

async function api(path, body, method = 'POST') {
  const opts = body === undefined ? {} : { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  const res = await fetch('/api' + path, opts);
  if (res.status === 401 && !path.startsWith('/login')) showLogin();
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).detail; } catch { /* ไม่มีรายละเอียด */ }
    throw new Error(typeof detail === 'string' && detail ? detail : 'เกิดข้อผิดพลาด ลองใหม่อีกครั้ง');
  }
  return res.json();
}

let toastTimer;
function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}

// ---------- สถานะของหน้า ----------
let S = null;            // ข้อมูลล่าสุดจากเซิร์ฟเวอร์
let lastJson = '';
let view = 'member';
let draftBags = [];      // ถุงที่ AI พบจากรูป สมาชิกแก้ไขได้ก่อนส่ง
let draftPhotos = [];    // [{thumb, note}] รูปที่แนบ พร้อมข้อความสรุปจาก AI
let analyzing = 0;       // จำนวนรูปที่ AI กำลังอ่านอยู่
let slot = null;
let pin = null;          // {lat, lng} จุดรับ
let pinMap, pinMarker, dMap, dLayer;
let dFitted = '';        // ขนาดแผนที่ตอนจัดมุมมองครั้งล่าสุด

const MAX_PHOTOS = 6;
const TAGS = 'ABCDEFGHJKLM';  // ต้องตรงกับ BAG_TAGS ใน app/config.py
const KIND = { bag: 'ถุง', bin: 'ถัง', box: 'กล่อง', pile: 'กอง' };

const material = (key) => S.config.materials[key] || { label: key, price: 0, unit_kg: 0, accepted: false };
const accepts = (key) => key !== 'non_recyclable' && material(key).accepted;
const slotLabel = (id) => (S.config.slots.find((s) => s.id === id) || {}).label || id;
const sumCount = (items) => items.reduce((a, i) => a + (i.material === 'non_recyclable' ? 0 : Math.max(0, parseInt(i.count, 10) || 0)), 0);
const itemsText = (items) => items.filter((i) => i.material !== 'non_recyclable').map((i) => `${esc(i.name_th)} ${num(i.count)} ชิ้น`).join(', ');
const bagTag = (r, b) => `${r.id}-${b.tag}`;

// สถานะของคำขอ: pending รอรับ -> verified คนขับสแกน QR ยืนยันจุดแล้ว -> collected รับของแล้ว -> delivered ส่งถึงศูนย์แล้ว
const STAGE = { pending: 0, verified: 1, collected: 2, delivered: 3 };
const isOpen = (r) => r.status === 'pending' || r.status === 'verified';
const isDone = (r) => r.status === 'collected' || r.status === 'delivered';

function statusText(r, st) {
  if (r.status === 'delivered') return 'ส่งถึงศูนย์คัดแยกแล้ว';
  if (r.status === 'collected') return 'รับของแล้ว';
  if (r.status === 'verified') return 'คนขับถึงจุดแล้ว กำลังตรวจของ';
  return st ? `${st.name} จุดที่ ${st.seq}` : 'ยังจัดรถไม่ลง';
}

function statusTag(r, st) {
  if (isDone(r)) return `<span class="badge gray">${statusText(r)} ${num(r.actual_kg, 1)} กก.</span>`;
  if (r.status === 'verified') return `<span class="badge info">${statusText(r)}</span>`;
  return st ? `<span class="badge">${esc(st.name)} ถึงประมาณ ${hhmm(st.eta)}</span>` : '<span class="badge warn">รอจัดรถ</span>';
}

// คำขอแต่ละรายการอยู่บนรถคันไหน ลำดับที่เท่าไร (เซิร์ฟเวอร์คำนวณให้ตามสิทธิ์ของบทบาท)
const stopIndex = () => S.stops || {};

async function refresh() {
  const res = await fetch('/api/state');
  if (res.status === 401) { showLogin(); return; }
  const text = await res.text();
  if (text === lastJson) return;
  lastJson = text;
  S = JSON.parse(text);
  renderAll();
}

let renderAll = function () {
  const badge = $('#ai-badge');
  badge.textContent = S.ai_mode === 'claude' ? 'AI: Claude Vision' : 'AI: โหมดจำลอง';
  badge.className = `badge ${S.ai_mode === 'claude' ? 'ai' : 'mock'}`;
  renderShell();
  const pages = {
    member: renderMember, dispatch: renderDispatch, records: renderRecords, prices: renderPrices, settings: renderSettings,
    partners: renderPartners, carbon: renderCarbon, portal: renderPortal,
    driver: () => { if (!driverBusy()) renderDriver(); },
  };
  pages[view]?.();
}

// ---------- สมาชิก ----------
const currentMember = () => S.me.member;

// QR ของแต่ละคำขอ โหลดเมื่อสมาชิกเปิดดู แล้วเก็บไว้ใช้ซ้ำ
const tickets = {};
const openTickets = new Set();
function ticketHtml(id) {
  const t = tickets[id];
  if (!t) return '<p class="muted">กำลังโหลด QR…</p>';
  return `<div class="qr">${t.svg}</div><p>รหัส <strong class="code">${esc(t.code)}</strong></p>
    <p class="muted">แสดง QR นี้ให้คนขับสแกนเมื่อมาถึง หรือบอกรหัสแทนได้</p>`;
}

function renderMember() {
  const me = currentMember();
  $('#member-kind').textContent = me.kind === 'company' ? 'บริษัท' : 'สมาชิก';
  $('#member-hello').textContent = me.kind === 'company' ? me.name : `สวัสดี ${me.name}`;
  $('#member-address').textContent = me.address;
  $('#member-points').textContent = num(me.points);

  if (!$('#slot-chips').children.length) {
    $('#slot-chips').innerHTML = S.config.slots.map((s) => `<button type="button" data-slot="${s.id}">${esc(s.label)}</button>`).join('');
  }
  if (!pinMap) initPinMap(me);

  const idx = stopIndex();
  const mine = [...S.requests].reverse();
  $('#my-requests').innerHTML = mine.length ? mine.map((r) => requestCard(r, idx[r.id])).join('')
    : '<div class="card"><p class="muted">ยังไม่มีคำขอ เริ่มจากถ่ายรูปถุงด้านบนได้เลย</p></div>';
}

function tagChips(r) {
  return r.bags.map((b) => {
    const cls = b.found === true ? 'ok' : b.found === false ? 'miss' : '';
    return `<span class="tag-chip ${cls}"><b>${bagTag(r, b)}</b>${esc(b.name_th)}${b.mismatch ? ' <span class="badge warn">ของไม่ตรง</span>' : ''}</span>`;
  }).join('');
}

// ขั้นล่าสุดของแต่ละคำขอที่เคยแสดง ใช้ให้ตราประทับ "ประทับลง" เฉพาะตอนที่ขั้นเปลี่ยน ไม่เล่นซ้ำทุกครั้งที่วาดหน้าใหม่
const seenStage = {};
function requestCard(r, st) {
  const stage = STAGE[r.status];
  const steps = ['แจ้งแล้ว', 'คนขับถึง', 'รับของแล้ว', 'ถึงศูนย์'];
  const stamps = ['แจ้งรับแล้ว', 'ยืนยันจุดแล้ว', 'ชั่งแล้ว', 'ถึงศูนย์แล้ว'];
  const fresh = seenStage[r.id] !== undefined && seenStage[r.id] !== stage;
  seenStage[r.id] = stage;
  const done = isDone(r);
  const found = r.bags.filter((b) => b.found !== false).length;
  const qr = isOpen(r)
    ? `<details class="ticket" data-ticket="${r.id}" ${openTickets.has(r.id) ? 'open' : ''}><summary>${ic('qr', 16)} QR สำหรับให้คนขับสแกน</summary><div class="qr-box">${ticketHtml(r.id)}</div></details>` : '';
  return `<article class="req">
    <div class="req-head"><strong>#${r.id}</strong><span class="slot-flag">${esc(slotLabel(r.slot))}</span></div>
    <ol class="timeline">${steps.map((t, n) => `<li class="${n < stage ? 'past' : n === stage ? `now${fresh ? ' fresh' : ''}` : ''}" ${n === stage ? `data-stamp="${stamps[n]}"` : ''}>${t}</li>`).join('')}</ol>
    <div class="fields">
      <div><span>ถุง</span><b>${num(done ? found : r.bags.length)}${done && found < r.bags.length ? `/${num(r.bags.length)}` : ''}</b></div>
      <div><span>ชิ้น</span><b>${num(r.total_count)}</b></div>
      <div><span>${done ? 'ชั่งจริง (กก.)' : 'ประเมิน (กก.)'}</span><b>${num(done ? r.actual_kg : r.est_kg, 1)}</b></div>
    </div>
    <div class="tag-row">${tagChips(r)}</div>
    <p class="muted">${done ? '' : `${statusTag(r, st)} · `}พิกัด ${coordLink(r.lat, r.lng)}</p>
    ${qr}</article>`;
}

function initPinMap(me) {
  pin = { lat: me.lat, lng: me.lng };
  pinMap = L.map('pinmap').setView([pin.lat, pin.lng], 15);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(pinMap);
  pinMarker = L.marker([pin.lat, pin.lng], { draggable: true }).addTo(pinMap);
  pinMarker.on('dragend', () => { const p = pinMarker.getLatLng(); setPin(p.lat, p.lng, false); });
  pinMap.on('click', (e) => setPin(e.latlng.lat, e.latlng.lng, false));
  setPin(pin.lat, pin.lng, false);
}

function setPin(lat, lng, recenter = true) {
  pin = { lat, lng };
  pinMarker.setLatLng([lat, lng]);
  if (recenter) pinMap.setView([lat, lng], 16);
  $('#pin-coords').textContent = coordText(lat, lng);
}

// ----- ถุงในคำขอที่กำลังกรอก -----
// สูตรเดียวกับ app/estimate.py: น้ำหนัก = จำนวนชิ้น x น้ำหนักเฉลี่ยต่อชิ้นของวัสดุ
function bagEst(b) {
  let total = 0, kg = 0, value = 0;
  for (const i of b.items) {
    const c = Math.max(0, parseInt(i.count, 10) || 0);
    const m = material(i.material);
    if (!m.accepted || !m.unit_kg || c === 0) continue;  // วัสดุที่เกณฑ์ปัจจุบันไม่รับ ไม่นับ
    total += c;
    kg += c * m.unit_kg;
    value += c * m.unit_kg * m.price;
  }
  return { total, kg, value };
}

const validBags = () => draftBags.filter((b) => bagEst(b).total > 0);

function bagCard(b, k) {
  const e = bagEst(b);
  const photo = b.photo != null ? draftPhotos[b.photo] : null;
  const flags = [
    b.count_method === 'estimate' ? '<span class="badge ai">นับโดยประมาณ</span>' : '<span class="badge">นับครบทุกชิ้น</span>',
    b.partial_view ? '<span class="badge warn">รูปเห็นไม่ทั้งถุง</span>' : '',
    b.mixed ? '<span class="badge warn">ของปนกัน ควรแยก</span>' : '',
  ].join('');
  const items = b.items.map((i, n) => {
    const rejected = !accepts(i.material);
    const control = rejected ? '<span class="badge danger">ไม่รับ</span>'
      : `<div class="stepper"><button type="button" data-step="-1" data-item="${n}" aria-label="ลดจำนวน ${esc(i.name_th)}">−</button>
           <input type="number" min="0" inputmode="numeric" value="${Number(i.count) || 0}" data-item="${n}" aria-label="จำนวน ${esc(i.name_th)}">
           <button type="button" data-step="1" data-item="${n}" aria-label="เพิ่มจำนวน ${esc(i.name_th)}">+</button></div>`;
    return `<li class="${rejected ? 'rejected' : ''}"><span class="dot mat-${esc(i.material)}"></span>
      <div><div class="name">${esc(i.name_th)}</div><div class="tip">${esc(material(i.material).label)}${i.prep_tip_th ? ` · ${esc(i.prep_tip_th)}` : ''}</div></div>${control}</li>`;
  }).join('');
  return `<article class="bag" data-bag="${k}">
    <div class="bag-head">
      <span class="tag-badge" title="ป้ายของถุงนี้">${TAGS[k] || '?'}</span>
      ${photo ? `<img class="bag-thumb" src="${photo.thumb}" alt="">` : ''}
      <div class="bag-title"><strong>${esc(b.name_th)}</strong><span class="muted">${esc(KIND[b.kind] || 'ถุง')}${b.position_th && b.position_th !== 'ทั้งรูป' ? ` · อยู่${esc(b.position_th)}ของรูป` : ''}</span></div>
      <button type="button" class="icon-btn" data-remove aria-label="ลบ${esc(b.name_th)}">${ic('trash')}</button>
    </div>
    <div class="flags">${flags}</div>
    <ul class="bag-items">${items}</ul>
    <div class="bag-foot">
      <div class="seg" role="group" aria-label="ขนาดถุง">${Object.keys(S.config.sizes).map((s) => `<button type="button" data-size="${s}" class="${s === b.size ? 'active' : ''}" title="${esc(S.config.sizes[s].label)}">${{ S: 'เล็ก', M: 'กลาง', L: 'ใหญ่' }[s]}</button>`).join('')}</div>
      <span class="bag-sum"><b>${num(e.total)}</b> ชิ้น · <b>${num(e.kg, 1)}</b> กก. · <b>${num(e.value, 1)}</b> บาท</span>
    </div></article>`;
}

function renderBags() {
  const notes = draftPhotos.map((p) => !p.note ? '' : `<div class="ai-note ${p.note.warning ? 'warn' : ''}"><img src="${p.thumb}" alt="รูปที่แนบ">
      <div><span class="badge ${p.note.warning ? 'warn' : 'ai'}">${ic('spark', 13)} ${p.note.warning ? 'ผลจำลอง' : 'AI'}</span> ${esc(p.note.summary)}
        ${p.note.warning ? `<span class="tip">${esc(p.note.warning)}</span>` : ''}
        ${p.note.tip ? `<span class="tip">${ic('camera', 13)} ${esc(p.note.tip)}</span>` : ''}</div></div>`).join('');
  $('#photo-notes').innerHTML = notes + (analyzing ? '<div class="ai-note loading"><span class="spinner"></span>AI กำลังนับถุง แยกชนิด และนับชิ้น…</div>' : '');
  $('#bags').innerHTML = draftBags.map(bagCard).join('');
  renderTotals();
}

function renderTotals() {
  const bags = validBags();
  const sum = bags.reduce((a, b) => { const e = bagEst(b); return { total: a.total + e.total, kg: a.kg + e.kg, value: a.value + e.value }; }, { total: 0, kg: 0, value: 0 });
  $('#bag-totals').innerHTML = !draftBags.length ? '' : `<div class="totals">
    <div><b>${num(bags.length)}</b><span>ถุง</span></div><div><b>${num(sum.total)}</b><span>ชิ้นที่รับได้</span></div>
    <div><b>${num(sum.kg, 1)}</b><span>กก. โดยประมาณ</span></div><div><b>${num(sum.value, 1)}</b><span>บาท โดยประมาณ</span></div></div>
    ${bags.length && sum.kg < S.config.min_request_kg ? `<div class="notice">น้ำหนักรวมต่ำกว่าขั้นต่ำ ${num(S.config.min_request_kg, 1)} กก. ${S.config.below_min_policy === 'block' ? 'จึงยังแจ้งรับไม่ได้ ลองรวมให้ได้มากขึ้น' : 'ระบบผ่อนปรนให้แจ้งได้ และจะบันทึกไว้ให้ผู้ดูแลทราบ'}</div>` : ''}`;
  $('#dropzone strong').textContent = draftBags.length ? 'เพิ่มรูปอีกถุง' : 'แตะเพื่อถ่ายหรือเลือกรูป';
  updateSubmit();
}

function updateSubmit() {
  $('#submit-request').disabled = !(validBags().length && slot && pin && !analyzing);
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('เปิดรูปนี้ไม่ได้ ลองใช้ไฟล์ JPG หรือ PNG')); };
    img.src = url;
  });
}

function scaled(img, max, quality) {
  const k = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight));
  const c = document.createElement('canvas');
  c.width = Math.round(img.naturalWidth * k);
  c.height = Math.round(img.naturalHeight * k);
  c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL('image/jpeg', quality);
}

async function handlePhoto(file) {
  if (draftPhotos.length >= MAX_PHOTOS) return toast(`แนบได้ไม่เกิน ${MAX_PHOTOS} รูปต่อคำขอ`);
  $('#submit-result').innerHTML = '';
  let photo;
  try {
    const img = await loadImage(file);
    const full = scaled(img, 1280, 0.85);              // ส่งให้ AI
    photo = { thumb: scaled(img, 320, 0.7), note: null };  // เก็บเป็นหลักฐานกับคำขอ
    const index = draftPhotos.push(photo) - 1;
    analyzing += 1;
    renderBags();
    const res = await api('/classify', { image_b64: full.split(',')[1], media_type: 'image/jpeg' });
    photo.note = { summary: res.summary_th, tip: res.photo_tip_th, warning: res.warning };
    for (const c of res.containers) {
      if (draftBags.length >= TAGS.length) { toast(`รับได้ไม่เกิน ${TAGS.length} ถุงต่อคำขอ`); break; }
      draftBags.push({ ...c, photo: index, items: c.items.map((i) => ({ ...i, ai_count: i.count })) });
    }
  } catch (err) {
    if (photo) photo.note = { summary: 'อ่านรูปนี้ไม่สำเร็จ', tip: '', warning: err.message };
    else toast(err.message);
  } finally {
    if (photo) analyzing -= 1;
    renderBags();
  }
}

async function handleFiles(files) {
  for (const f of files) await handlePhoto(f);  // ทีละรูป เพื่อให้ป้ายถุงเรียงตามลำดับที่แนบ
}

async function submitRequest() {
  const btn = $('#submit-request');
  btn.disabled = true;
  try {
    const bags = validBags();
    // ส่งเฉพาะรูปที่ยังมีถุงอ้างถึง แล้วเรียงลำดับรูปใหม่
    const used = [...new Set(bags.map((b) => b.photo).filter((p) => p != null))];
    const body = {
      lat: pin.lat, lng: pin.lng, slot,
      photos: used.map((p) => draftPhotos[p].thumb),
      bags: bags.map((b) => ({
        name_th: b.name_th, position_th: b.position_th, kind: b.kind, mixed: b.mixed, size: b.size,
        count_method: b.count_method, partial_view: b.partial_view, photo: b.photo == null ? null : used.indexOf(b.photo),
        items: b.items.map((i) => ({ name_th: i.name_th, material: i.material, count: Math.max(0, parseInt(i.count, 10) || 0), ai_count: i.ai_count, prep_tip_th: i.prep_tip_th })),
      })),
    };
    const res = await api('/requests', body);
    const r = res.request;
    try { tickets[r.id] = await api(`/requests/${r.id}/ticket`); } catch { /* เปิดดู QR ได้จากรายการคำขอ */ }
    $('#submit-result').innerHTML = `<div class="card success">
      <div class="success-head"><span class="stamp">แจ้งรับแล้ว</span>
        <div><h2>แจ้งรับเรียบร้อย เลขที่ #${r.id}</h2>
        <p class="muted">${res.stop ? `${esc(res.stop.vehicle)} จะถึงประมาณ ${hhmm(res.stop.eta)} (จุดที่ ${res.stop.seq} ของรอบ)` : 'ช่วงเวลานี้ยังจัดรถไม่ลง ผู้จัดรถจะติดต่อกลับ'}</p></div></div>
      <h3>เขียนป้ายบนถุงแต่ละใบ</h3>
      <p class="muted">ใช้ปากกาเมจิกหรือแปะกระดาษ คนขับจะตรวจรับตามป้ายนี้</p>
      <ul class="tag-list">${r.bags.map((b) => `<li><span class="tag-badge big">${bagTag(r, b)}</span>
        ${b.photo != null ? `<img class="bag-thumb" src="/api/requests/${r.id}/photo/${b.photo}" alt="">` : ''}
        <div><div class="name">${esc(b.name_th)}</div><span class="muted">${itemsText(b.items)}</span></div></li>`).join('')}</ul>
      <p class="muted" style="margin-top:.7rem">รวม ${num(r.bags.length)} ถุง ${num(r.total_count)} ชิ้น · พิกัด ${coordLink(r.lat, r.lng)}</p>
      ${tickets[r.id] ? `<div class="qr-box">${ticketHtml(r.id)}</div>` : ''}
    </div>`;
    draftBags = []; draftPhotos = [];
    renderBags();
    await refresh();
    $('#submit-result').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    toast(err.message);
    updateSubmit();
  }
}

// ---------- ผู้จัดรถ ----------
function pinIcon(text, color, cls = '') {
  return L.divIcon({ className: '', html: `<div class="pin ${cls}" style="background:${color}">${ICONS[text] ? ic(text, 15) : esc(text)}</div>`, iconSize: [28, 28], iconAnchor: [14, 14] });
}

function renderDispatch() {
  if (!dMap) {
    dMap = L.map('dispatch-map').setView([S.config.depot.lat, S.config.depot.lng], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(dMap);
    dLayer = L.layerGroup().addTo(dMap);
  }
  dMap.invalidateSize();
  dLayer.clearLayers();

  const depot = S.config.depot;
  const plan = S.plan || { routes: [], unassigned: [], factory_kg: [] };
  const idx = stopIndex();
  const byId = Object.fromEntries(S.requests.map((r) => [r.id, r]));
  const bounds = [[depot.lat, depot.lng]];
  const now = Date.now() / 1000;

  for (const route of plan.routes) {
    const path = [[depot.lat, depot.lng], ...route.stops.map((s) => [byId[s.request_id].lat, byId[s.request_id].lng]), [depot.lat, depot.lng]];
    if (route.stops.length) L.polyline(path, { color: route.color, weight: 4, opacity: 0.75 }).addTo(dLayer);
  }
  const dayStart = new Date().setHours(0, 0, 0, 0) / 1000;
  const shown = S.requests.filter((r) => isOpen(r) || (r.collected_at || r.created_at) >= dayStart);  // ไม่เอาประวัติย้อนหลังขึ้นแผนที่
  for (const r of shown) {
    const st = idx[r.id];
    const done = isDone(r);
    const here = r.status === 'verified';
    const fresh = now - r.created_at < 90 ? 'new' : '';
    const icon = done ? pinIcon('check', '#8a95a0', 'done') : st ? pinIcon(st.seq, st.color, `${fresh} ${here ? 'here' : ''}`) : pinIcon('alert', '#c8102e', fresh);
    const where = done ? `${statusText(r)} ${num(r.actual_kg, 1)} กก.` : here ? statusText(r) : st ? `${esc(st.name)} · ถึงประมาณ ${hhmm(st.eta)}` : 'ยังจัดรถไม่ลง';
    L.marker([r.lat, r.lng], { icon }).addTo(dLayer).bindPopup(
      `<strong>#${r.id} ${esc(r.member_name)}</strong><br>${where}<br>นัด ${esc(slotLabel(r.slot))}<br>
       ${num(r.bags.length)} ถุง: ${r.bags.map((b) => bagTag(r, b)).join(', ')}<br>
       ${itemsText(r.items)}<br>รวม ${num(r.total_count)} ชิ้น · ประมาณ ${num(r.est_kg, 1)} กก.<br>พิกัด ${coordLink(r.lat, r.lng)}`);
    bounds.push([r.lat, r.lng]);
  }
  L.marker([depot.lat, depot.lng], { icon: pinIcon('ศ', '#18202a', 'depot') }).addTo(dLayer).bindPopup(esc(depot.name));
  // จัดมุมมองให้เห็นทุกหมุดครั้งแรก และจัดใหม่เมื่อขนาดแผนที่เปลี่ยน (เช่น หมุนจอหรือย่อขยายหน้าต่าง)
  const box = dMap.getSize();
  const fitKey = `${box.x}x${box.y}`;
  if (dFitted !== fitKey) { dMap.fitBounds(bounds, { padding: [24, 24] }); dFitted = fitKey; }

  const pending = S.requests.filter(isOpen);
  const stops = plan.routes.reduce((a, r) => a + r.stops.filter((s) => byId[s.request_id] && isOpen(byId[s.request_id])).length, 0);
  renderDashWidgets(plan, pending, stops);
  $('#plan-summary').textContent = plan.summary || '';

  const routeOf = Object.fromEntries(plan.routes.map((r) => [r.vehicle_id, r]));
  $('#vehicle-list').innerHTML = S.vehicles.map((v) => {
    const r = routeOf[v.id];
    const used = r ? Math.round((r.load_units / v.capacity_units) * 100) : 0;
    const info = !v.active ? '<span class="badge warn">หยุดใช้งาน</span>'
      : r && r.stops.length ? `<div class="bar"><span style="width:${used}%;background:${esc(v.color)}"></span></div>
          <span class="muted">${r.stops.length} จุด · ${num(r.km, 1)} กม. · ใช้พื้นที่ ${num(r.load_units)}/${num(v.capacity_units)} ถุง · กลับถึงศูนย์ ${hhmm(r.back_at)}</span>`
      : '<span class="muted">ไม่มีงาน</span>';
    return `<div class="list-item"><div class="veh-head"><span class="veh-dot" style="background:${esc(v.color)}"></span><strong>${esc(v.name)}</strong></div>${info}</div>`;
  }).join('');

  const latest = [...shown].sort((a, b) => b.created_at - a.created_at).slice(0, 6);
  $('#feed').innerHTML = latest.map((r) => `<div class="list-item"><strong>${esc(r.member_name)}</strong> แจ้งรับ #${r.id} <span class="muted">${timeText(r.created_at)}</span><br>
      พิกัด ${coordLink(r.lat, r.lng)}<br>
      <strong>${num(r.bags.length)} ถุง · ${num(r.total_count)} ชิ้น</strong> ${itemsText(r.items)}<br>
      <span class="muted">นัด ${esc(slotLabel(r.slot))} · ${esc(statusText(r, idx[r.id]))}</span></div>`).join('');

  $('#factory-list').innerHTML = (plan.factory_kg || []).map((f) =>
    `<div class="list-item">${esc(f.name)}<br><span class="muted">ประมาณ ${num(f.kg, 1)} กก.</span></div>`).join('')
    + '<p class="muted" style="margin-top:.6rem">รถทุกคันกลับมาส่งที่ศูนย์คัดแยก แล้วแยกส่งโรงงานตามชนิดวัสดุ</p>';

  const flagged = [...S.requests].filter((r) => r.flags.length).reverse().slice(0, 8);
  $('#flag-list').innerHTML = flagged.length ? flagged.map((r) => `<div class="list-item"><strong>#${r.id} ${esc(r.member_name)}</strong>
      <div class="tag-row">${r.flags.map((f) => `<span class="badge warn">${esc(S.config.flags[f] || f)}</span>`).join('')}</div></div>`).join('')
    : '<p class="muted">ยังไม่มีกรณีที่ต้องดู</p>';
}

// ---------- คนขับรถรับของ ----------
// ขั้นตอนต่อหนึ่งจุด: นำทาง -> ถึงจุด สแกน QR ของลูกค้า (ยืนยันจุด) -> ตรวจรับทีละถุงตามป้ายและชั่งน้ำหนัก (ยืนยันของ)
// เมื่อรับครบ: กลับศูนย์คัดแยก แล้วกดส่งของเพื่อปิดรอบ
let scanFor = null;     // เลขคำขอที่กำลังเปิดหน้าสแกน
let scanStream = null;
let scanTimer = null;
let scanBusy = false;

// ระหว่างสแกนหรือกำลังพิมพ์ตัวเลข ไม่วาดหน้าใหม่ เพื่อไม่ให้กล้องดับหรือค่าที่พิมพ์หาย
const driverBusy = () => scanFor !== null || !!document.activeElement?.closest?.('#driver-stops input');

function renderDriver() {
  const veh = S.me.vehicle;
  const vid = veh.id;
  const route = S.route;
  $('#driver-name').textContent = veh.name;
  const byId = Object.fromEntries(S.requests.map((r) => [r.id, r]));
  const stops = (route?.stops || []).map((s) => ({ ...s, r: byId[s.request_id] })).filter((s) => s.r);
  const open = stops.filter((s) => isOpen(s.r));
  const onTruck = S.requests.filter((r) => r.status === 'collected' && r.vehicle_id === vid);
  const total = open.length + onTruck.length;
  $('#driver-progress').style.width = total ? `${Math.round((onTruck.length / total) * 100)}%` : '0%';

  $('#driver-summary').textContent = !veh?.active ? 'รถคันนี้หยุดใช้งานอยู่'
    : open.length ? `เหลือ ${open.length} จุด · รับแล้ว ${onTruck.length} จุด · ระยะทางรอบนี้ ${num(route.km, 1)} กม.`
    : onTruck.length ? 'รับครบทุกจุดแล้ว กลับไปส่งของที่ศูนย์คัดแยก' : 'ยังไม่มีงานในรอบนี้';

  const nextId = open[0]?.r.id;
  $('#driver-stops').innerHTML = veh?.active ? stops.map((s, n) => stopCard(s, n, s.r.id === nextId)).join('') : '';
  renderDriverEnd(vid, open, onTruck);
  renderDriverMap(veh?.active ? stops : [], nextId);
}

const thumb = (r, b) => (b.photo != null ? `<img class="bag-thumb" src="/api/requests/${r.id}/photo/${b.photo}" alt="รูปที่สมาชิกแนบ" loading="lazy">` : '');

function checkBag(r, b) {
  return `<li class="check-bag" data-check="${r.id}" data-tag="${esc(b.tag)}">
    <div class="check-top"><span class="tag-badge">${bagTag(r, b)}</span>${thumb(r, b)}
      <div class="grow"><div class="name">${esc(b.name_th)}</div><div class="tip">${itemsText(b.items)}</div></div></div>
    <div class="check-controls">
      <label class="switch"><input type="checkbox" data-found checked><span>พบถุงนี้</span></label>
      <div class="check-inputs">
        <label class="kg"><input type="number" min="0.1" step="0.1" inputmode="decimal" value="${Math.max(0.1, Number(b.est_kg)).toFixed(1)}" data-kg aria-label="น้ำหนักจริงของถุง ${bagTag(r, b)}">กก.</label>
        <label class="mini"><input type="checkbox" data-mismatch>ของไม่ตรง</label>
      </div>
    </div></li>`;
}

function stopCard(s, n, isNext) {
  const r = s.r;
  let body;
  if (isDone(r)) {
    const found = r.bags.filter((b) => b.found).length;
    body = `<div class="notice ok">รับแล้ว ${num(found)}/${num(r.bags.length)} ถุง · ${num(r.actual_kg, 1)} กก.</div><div class="tag-row">${tagChips(r)}</div>`;
  } else if (r.status === 'verified') {
    const far = r.verify_distance_m != null && r.verify_distance_m > 200;
    body = `<div class="notice ${far ? '' : 'ok'}">ยืนยันจุดแล้ว ${timeText(r.verified_at)}${r.verify_distance_m != null ? ` · สแกนห่างจากหมุด ${num(r.verify_distance_m)} ม.${far ? ' ซึ่งไกลกว่าปกติ' : ''}` : ''}</div>
      <h3>ตรวจรับทีละถุงตามป้าย</h3>
      <p class="muted">เทียบป้ายบนถุงกับรายการ ปิดสวิตช์ถ้าไม่พบถุง แล้วใส่น้ำหนักจริง</p>
      <ul class="check-list">${r.bags.map((b) => checkBag(r, b)).join('')}</ul>
      <button type="button" class="btn primary block" data-collect="${r.id}">ยืนยันรับของ</button>`;
  } else if (scanFor === r.id) {
    body = `<div class="scanner">
      <p><strong>สแกน QR จากมือถือของลูกค้า</strong> เพื่อยืนยันว่ามาถูกจุด</p>
      <video id="scan-video" playsinline muted hidden></video>
      <div class="row">
        <button type="button" class="btn primary small" data-scan="camera">${ic('camera', 16)} เปิดกล้องสแกน</button>
        <label class="btn ghost small" for="scan-file">แนบรูป QR</label>
        <input id="scan-file" type="file" accept="image/*" hidden>
      </div>
      <form class="row" id="scan-form">
        <input type="text" id="scan-code" placeholder="รหัส 6 ตัว" maxlength="6" autocomplete="off" autocapitalize="characters" aria-label="รหัสรับของ 6 ตัว">
        <button type="submit" class="btn ghost small">ยืนยันรหัส</button>
      </form>
      <p id="scan-msg" class="muted" role="status"></p>
      <div><button type="button" class="btn ghost small" data-scan="cancel">ยกเลิก</button></div>
    </div>`;
  } else {
    body = `<div class="tag-row">${tagChips(r)}</div>
      <div class="row actions"><button type="button" class="btn ghost small" data-nav="${r.id}">${ic('nav', 15)} นำทาง</button>
      <button type="button" class="btn ${isNext ? 'primary' : 'ghost'} small" data-arrive="${r.id}">${ic('qr', 15)} ถึงจุดแล้ว สแกน QR</button></div>`;
  }
  return `<div id="stop-${r.id}" class="card stop ${isDone(r) ? 'done' : ''} ${isNext ? 'next' : ''}">
    <div class="seq">${n + 1}</div>
    <div>
      <span class="stop-title">${hhmm(s.eta)} · ${esc(r.member_name)}</span><br>
      <span class="muted">${esc(r.address)} · นัด ${esc(slotLabel(r.slot))} · พิกัด ${coordLink(r.lat, r.lng)}</span><br>
      <span class="muted">${num(r.bags.length)} ถุง · ${num(r.total_count)} ชิ้น · ประมาณ ${num(r.est_kg, 1)} กก.</span>
      ${body}
    </div></div>`;
}

function renderDriverEnd(vid, open, onTruck) {
  const depot = S.config.depot;
  const last = [...(S.dropoffs || [])].reverse().find((d) => d.vehicle_id === vid);
  let out = '';
  if (onTruck.length) {
    const kg = onTruck.reduce((a, r) => a + (r.actual_kg || 0), 0);
    const bags = onTruck.reduce((a, r) => a + r.bags.filter((b) => b.found).length, 0);
    out += `<div class="card ${open.length ? '' : 'next'}">
      <h2>${open.length ? 'ของบนรถตอนนี้' : 'รับครบแล้ว กลับศูนย์คัดแยก'}</h2>
      <p>${num(onTruck.length)} จุด · ${num(bags)} ถุง · ${num(kg, 1)} กก.</p>
      <p class="muted">${esc(depot.name)} · พิกัด ${coordLink(depot.lat, depot.lng)}</p>
      <div class="row actions"><button type="button" class="btn ghost small" data-nav="depot">${ic('nav', 15)} นำทางไปศูนย์</button>
        <button type="button" class="btn ${open.length ? 'ghost' : 'primary'} small" data-dropoff="${vid}" data-open="${open.length}">ส่งของที่ศูนย์แล้ว</button></div></div>`;
  }
  if (last) {
    out += `<div class="card"><h2>รอบที่ส่งล่าสุด</h2>
      <p>${timeText(last.at)} · ${num(last.stops)} จุด · ${num(last.bags)} ถุง · ${num(last.pieces)} ชิ้น · ${num(last.kg, 1)} กก.</p>
      ${last.factories.filter((f) => f.kg > 0).map((f) => `<div class="list-item">${esc(f.name)}<br><span class="muted">${num(f.kg, 1)} กก.</span></div>`).join('')}</div>`;
  }
  $('#driver-end').innerHTML = out;
}

// ----- สแกน QR -----
function scanMsg(text) { const el = $('#scan-msg'); if (el) el.textContent = text; }

function stopCamera() {
  clearInterval(scanTimer);
  scanTimer = null;
  if (scanStream) scanStream.getTracks().forEach((t) => t.stop());
  scanStream = null;
}

async function decodeQR(source, w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const g = c.getContext('2d', { willReadFrequently: true });
  g.fillStyle = '#fff';
  g.fillRect(0, 0, w, h);
  g.drawImage(source, 0, 0, w, h);
  if ('BarcodeDetector' in window) {
    try {
      const hits = await new BarcodeDetector({ formats: ['qr_code'] }).detect(c);
      if (hits.length) return hits[0].rawValue;
    } catch { /* ใช้ตัวอ่านสำรองด้านล่าง */ }
  }
  if (window.jsQR) {
    const hit = jsQR(g.getImageData(0, 0, w, h).data, w, h);
    if (hit) return hit.data;
  }
  return null;
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) return scanMsg('อุปกรณ์นี้เปิดกล้องจากหน้าเว็บไม่ได้ (ต้องเป็น HTTPS หรือ localhost) ใช้แนบรูป QR หรือพิมพ์รหัสแทน');
  try {
    scanStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
  } catch { return scanMsg('เปิดกล้องไม่ได้ ใช้แนบรูป QR หรือพิมพ์รหัสแทน'); }
  const video = $('#scan-video');
  if (!video) return stopCamera();
  video.srcObject = scanStream;
  video.hidden = false;
  await video.play().catch(() => {});
  scanMsg('หันกล้องไปที่ QR บนมือถือของลูกค้า');
  scanTimer = setInterval(async () => {
    if (scanBusy || video.readyState < 2) return;
    scanBusy = true;
    try {
      const value = await decodeQR(video, video.videoWidth, video.videoHeight);
      if (value) await submitScan(value);
    } finally { scanBusy = false; }
  }, 350);
}

async function scanFromFile(file) {
  try {
    const img = await loadImage(file);
    const k = Math.min(1, 1200 / Math.max(img.naturalWidth, img.naturalHeight));
    const value = await decodeQR(img, Math.round(img.naturalWidth * k), Math.round(img.naturalHeight * k));
    if (!value) return scanMsg('อ่าน QR จากรูปนี้ไม่ได้ ลองรูปที่ชัดขึ้น หรือพิมพ์รหัสแทน');
    await submitScan(value);
  } catch (err) { scanMsg(err.message); }
}

// ตำแหน่งของคนขับตอนสแกน ถ้าอุปกรณ์ให้ได้ภายใน 1.5 วินาที ใช้บันทึกว่าสแกนห่างจากหมุดเท่าไร
function driverPosition() {
  return new Promise((resolve) => {
    if (!navigator.geolocation || !window.isSecureContext) return resolve(null);
    const timer = setTimeout(() => resolve(null), 1500);
    navigator.geolocation.getCurrentPosition(
      (p) => { clearTimeout(timer); resolve({ lat: p.coords.latitude, lng: p.coords.longitude }); },
      () => { clearTimeout(timer); resolve(null); },
      { maximumAge: 30000, timeout: 1500 });
  });
}

async function submitScan(value) {
  const id = scanFor;
  if (!id) return;
  scanMsg('กำลังตรวจรหัส…');
  try {
    const pos = await driverPosition();
    await api(`/requests/${id}/verify`, { scan: value, ...(pos || {}) });
    stopCamera();
    scanFor = null;
    toast('ยืนยันจุดแล้ว ตรวจรับทีละถุงได้เลย');
    await refresh();
    renderDriver();
  } catch (err) { scanMsg(err.message); }
}

async function collectStop(id, btn) {
  const bags = [...document.querySelectorAll(`[data-check="${id}"]`)].map((li) => ({
    tag: li.dataset.tag,
    found: $('[data-found]', li).checked,
    kg: Number($('[data-kg]', li).value) || 0,
    mismatch: $('[data-mismatch]', li).checked,
  }));
  btn.disabled = true;
  try {
    const res = await api(`/requests/${id}/collect`, { bags });
    toast(`รับแล้ว ${num(res.found)}/${num(res.bags)} ถุง สมาชิกได้รับ ${num(res.points)} แต้ม${res.flags.length ? ' · มีรายการให้ผู้ดูแลตรวจ' : ''}`);
    document.activeElement?.blur();
    await refresh();
    renderDriver();
  } catch (err) { toast(err.message); btn.disabled = false; }
}

// ---------- บันทึก ----------
function renderRecords() {
  const idx = stopIndex();
  const rows = [...S.requests].reverse();
  const collected = rows.filter(isDone);
  $('#records-totals').innerHTML = `
    <div class="stat"><b>${num(rows.length)}</b><span>คำขอทั้งหมด</span></div>
    <div class="stat"><b>${num(rows.reduce((a, r) => a + r.bags.length, 0))}</b><span>ถุงที่แจ้ง</span></div>
    <div class="stat"><b>${num(rows.reduce((a, r) => a + r.total_count, 0))}</b><span>ชิ้นที่แจ้ง</span></div>
    <div class="stat accent"><b>${num(collected.length)}</b><span>คำขอที่รับแล้ว</span></div>
    <div class="stat accent"><b>${num(collected.reduce((a, r) => a + (r.actual_kg || 0), 0), 1)} กก.</b><span>น้ำหนักจริงที่รับ</span></div>`;
  $('#records-table').innerHTML = `<thead><tr>
      <th>เลขที่</th><th>เวลาแจ้ง</th><th>สมาชิก</th><th>พิกัด</th><th>ช่วงนัด</th><th>ถุงและป้าย</th>
      <th>รวม (ชิ้น)</th><th>ประมาณ (กก.)</th><th>ยืนยันจุด</th><th>พบถุง</th><th>จริง (กก.)</th><th>สถานะ</th></tr></thead><tbody>${rows.map((r) => {
    const st = idx[r.id];
    const status = isDone(r) || r.status === 'verified' ? `<span class="badge ${isDone(r) ? 'gray' : 'info'}">${statusText(r)}</span>`
      : st ? `<span class="badge">${esc(st.name)}</span>` : '<span class="badge warn">รอจัดรถ</span>';
    return `<tr><td>#${r.id}</td><td>${timeText(r.created_at)}</td><td>${esc(r.member_name)}</td><td>${coordLink(r.lat, r.lng)}</td>
      <td>${esc(slotLabel(r.slot))}</td><td><div class="tag-row" style="margin:0">${tagChips(r)}</div></td><td class="num">${num(r.total_count)}</td>
      <td class="num">${num(r.est_kg, 1)}</td><td>${r.verified_at ? timeText(r.verified_at) : '–'}</td>
      <td class="num">${isDone(r) ? `${num(r.bags.filter((b) => b.found).length)}/${num(r.bags.length)}` : '–'}</td>
      <td class="num">${r.actual_kg ? num(r.actual_kg, 1) : '–'}</td><td>${status}</td></tr>`;
  }).join('')}</tbody>`;
}

// ---------- การสลับหน้าและเหตุการณ์ ----------
function show(next) {
  const allowed = TABS[S.me.role].map((t) => t.id);
  view = allowed.includes(next) ? next : allowed[0];
  for (const el of document.querySelectorAll('main > section')) el.hidden = el.id !== `view-${view}`;
  if (view !== 'driver') { stopCamera(); scanFor = null; }
  if (location.hash.slice(1) !== view) history.replaceState(null, '', '#' + view);
  renderAll();
  if (view === 'member' && pinMap) pinMap.invalidateSize();
  window.scrollTo(0, 0);
}

$('#tabs').addEventListener('click', (e) => { const b = e.target.closest('[data-view]'); if (b) show(b.dataset.view); });
window.addEventListener('hashchange', () => { if (S) show(location.hash.slice(1)); });

$('#photo').addEventListener('change', (e) => { const files = [...e.target.files]; e.target.value = ''; handleFiles(files); });
const dz = $('#dropzone');
dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.classList.add('over'); });
dz.addEventListener('dragleave', () => dz.classList.remove('over'));
dz.addEventListener('drop', (e) => { e.preventDefault(); dz.classList.remove('over'); handleFiles([...e.dataTransfer.files].filter((f) => f.type.startsWith('image/'))); });
$('#use-gps').addEventListener('click', () => {
  if (!navigator.geolocation) return toast('อุปกรณ์นี้ไม่รองรับการระบุตำแหน่ง');
  navigator.geolocation.getCurrentPosition((p) => setPin(p.coords.latitude, p.coords.longitude), () => toast('อ่านตำแหน่งไม่ได้ ลากหมุดบนแผนที่แทน'));
});
$('#slot-chips').addEventListener('click', (e) => {
  if (!e.target.dataset.slot) return;
  slot = e.target.dataset.slot;
  document.querySelectorAll('#slot-chips button').forEach((c) => c.classList.toggle('active', c.dataset.slot === slot));
  updateSubmit();
});

// แก้ถุง: เปลี่ยนจำนวน ขนาด หรือลบถุง
function refreshBag(k) {
  const el = $(`[data-bag="${k}"]`);
  const e = bagEst(draftBags[k]);
  $('.bag-sum', el).innerHTML = `<b>${num(e.total)}</b> ชิ้น · <b>${num(e.kg, 1)}</b> กก. · <b>${num(e.value, 1)}</b> บาท`;
  renderTotals();
}
$('#bags').addEventListener('click', (e) => {
  const bagEl = e.target.closest('[data-bag]');
  if (!bagEl) return;
  const k = Number(bagEl.dataset.bag);
  const btn = e.target.closest('button');
  if (!btn) return;
  if (btn.dataset.remove !== undefined) { draftBags.splice(k, 1); renderBags(); }
  else if (btn.dataset.size) {
    draftBags[k].size = btn.dataset.size;
    bagEl.querySelectorAll('[data-size]').forEach((c) => c.classList.toggle('active', c.dataset.size === btn.dataset.size));
  } else if (btn.dataset.step) {
    const item = draftBags[k].items[Number(btn.dataset.item)];
    item.count = Math.max(0, (parseInt(item.count, 10) || 0) + Number(btn.dataset.step));
    $(`input[data-item="${btn.dataset.item}"]`, bagEl).value = item.count;
    refreshBag(k);
  }
});
$('#bags').addEventListener('input', (e) => {
  if (e.target.dataset.item === undefined) return;
  const k = Number(e.target.closest('[data-bag]').dataset.bag);
  draftBags[k].items[Number(e.target.dataset.item)].count = e.target.value;
  refreshBag(k);
});
$('#submit-request').addEventListener('click', submitRequest);

$('#my-requests').addEventListener('toggle', async (e) => {
  const id = Number(e.target.dataset?.ticket);
  if (!id) return;
  if (!e.target.open) { openTickets.delete(id); return; }
  openTickets.add(id);
  if (!tickets[id]) {
    try { tickets[id] = await api(`/requests/${id}/ticket`); } catch (err) { return toast(err.message); }
  }
  e.target.querySelector('.qr-box').innerHTML = ticketHtml(id);
}, true);  // toggle ไม่ bubble จึงต้องจับในช่วง capture

$('#replan').addEventListener('click', async () => {
  try { const p = await api('/plan', {}); await refresh(); toast(p.summary); } catch (err) { toast(err.message); }
});
$('#reset').addEventListener('click', async () => {
  if (!confirm('ล้างข้อมูลทั้งหมดแล้วกลับไปใช้ข้อมูลตัวอย่างใช่ไหม')) return;
  try { await api('/reset', {}); dFitted = ''; await refresh(); toast('รีเซ็ตข้อมูลแล้ว'); } catch (err) { toast(err.message); }
});
async function sendCommand(text) {
  $('#command-reply').textContent = 'กำลังประมวลผล…';
  try {
    const res = await api('/command', { text });
    $('#command-reply').textContent = res.reply + (res.source === 'rule' ? ' (ตีความด้วยกฎคำสำคัญ เพราะยังไม่ได้ตั้งค่า AI)' : '');
    if (res.ok) $('#command-text').value = '';
    await refresh();
  } catch (err) { $('#command-reply').textContent = err.message; }
}
$('#command-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const text = $('#command-text').value.trim();
  if (text) sendCommand(text);
});
$('#command-suggest').addEventListener('click', (e) => {
  if (e.target.tagName !== 'BUTTON') return;
  $('#command-text').value = e.target.textContent;
  sendCommand(e.target.textContent);
});

$('#driver-stops').addEventListener('click', (e) => {
  const d = (e.target.closest('button') || e.target).dataset;
  if (d.nav) openNav(d.nav === 'depot' ? 'depot' : Number(d.nav));
  else if (d.arrive) { stopCamera(); scanFor = Number(d.arrive); renderDriver(); $('#scan-code')?.focus(); }
  else if (d.scan === 'camera') startCamera();
  else if (d.scan === 'cancel') { stopCamera(); scanFor = null; renderDriver(); }
  else if (d.collect) collectStop(Number(d.collect), e.target.closest('button'));
});
$('#driver-stops').addEventListener('submit', (e) => {
  if (e.target.id !== 'scan-form') return;
  e.preventDefault();
  const code = $('#scan-code').value.trim();
  if (code) submitScan(code);
});
$('#driver-stops').addEventListener('change', (e) => {
  if (e.target.id === 'scan-file') {
    const f = e.target.files[0];
    e.target.value = '';
    if (f) scanFromFile(f);
  } else if (e.target.dataset.found !== undefined) {
    e.target.closest('.check-bag').classList.toggle('off', !e.target.checked);  // ไม่พบถุง: ไม่ต้องกรอกน้ำหนัก
  }
});
$('#driver-end').addEventListener('click', async (e) => {
  if (e.target.closest('[data-nav]')) return openNav('depot');
  const btn = e.target.closest('[data-dropoff]');
  if (!btn) return;
  if (Number(btn.dataset.open) > 0 && !confirm('ยังมีจุดที่ยังไม่ได้รับ ต้องการส่งของที่ศูนย์ตอนนี้ใช่ไหม')) return;
  btn.disabled = true;
  try {
    const res = await api('/dropoff', {});
    toast(`ส่งของแล้ว ${num(res.stops)} จุด ${num(res.bags)} ถุง รวม ${num(res.kg, 1)} กก.`);
    await refresh();
    renderDriver();
  } catch (err) { toast(err.message); btn.disabled = false; }
});

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
}
