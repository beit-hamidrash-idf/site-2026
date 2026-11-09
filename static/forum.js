// Discussion forum for Beit HaMidrash. Loaded on demand when the page opens #forum.
// Data lives in Firebase (Firestore + Google sign-in); permissions are enforced by forum/firestore.rules.
const V = "10.12.2";
const FB = `https://www.gstatic.com/firebasejs/${V}`;
const DEFAULT_CATS = [["shabbat","שבת"],["kashrut","כשרות"],["tfila","תפילה וברכות"],["moadim","מועדים"],["army","הלכה בשירות"],["general","שאלות כלליות"]];
const DEFAULT_RULES = "הפורום נועד לדיון בהלכה. כתבו בכבוד, בלי לשון הרע ובלי פרסום.\nאין לציין שמות יחידות, מיקומים, פעילויות מבצעיות או כל מידע מסווג.\nשאלה הלכתית למעשה – כדאי לשאול גם רב.";
const ROLE = { admin: "מנהל ראשי", mod: "מנהל", user: "" };

let fb, auth, db, root, cfg;
const S = { user: null, profile: null, settings: { moderation: true, rules: "" }, cats: [], ready: false };
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtBody = s => esc(s).replace(/https?:\/\/[^\s<]+/g, u => `<a href="${u}" target="_blank" rel="noopener nofollow">${u}</a>`).replace(/\n/g, "<br>");
const rtf = new Intl.RelativeTimeFormat("he", { numeric: "auto" });
function ago(ts){
  const d = ts?.toDate ? ts.toDate() : null; if (!d) return "עכשיו";
  const s = (d - Date.now()) / 1000, a = Math.abs(s);
  if (a < 60) return "עכשיו";
  if (a < 3600) return rtf.format(Math.round(s/60), "minute");
  if (a < 86400) return rtf.format(Math.round(s/3600), "hour");
  if (a < 86400*30) return rtf.format(Math.round(s/86400), "day");
  return d.toLocaleDateString("he-IL");
}
const isMod = () => S.profile && !S.profile.banned && (S.profile.role === "mod" || S.profile.role === "admin");
const isAdmin = () => S.profile && S.profile.role === "admin";
const canWrite = () => S.profile && !S.profile.banned;
const catName = id => (S.cats.find(c => c.id === id) || {}).name || "";
function toast(msg, bad){
  const t = document.createElement("div"); t.className = "fm-toast" + (bad ? " bad" : ""); t.setAttribute("role", "status"); t.textContent = msg;
  document.body.appendChild(t); setTimeout(() => t.remove(), 3800);
}
const fail = e => { console.error(e); toast(e?.code === "permission-denied" ? "אין הרשאה לפעולה הזו." : "משהו השתבש. נסו שוב.", true); };
const go = h => { if (location.hash === h) route(); else location.hash = h; };

export async function mount(el){
  root = el;
  if (S.ready) return route();
  root.innerHTML = `<p class="fm-muted">טוען את הפורום…</p>`;
  try { cfg = await (await fetch("forum-config.json", { cache: "no-store" })).json(); } catch(e) { cfg = {}; }
  if (!cfg.firebase){
    root.innerHTML = `<div class="fm-empty"><h2>הפורום בהקמה</h2><p>הפורום יופעל בקרוב. בינתיים אפשר לשאול את הרב או לשלוח משוב דרך התפריט.</p></div>`;
    return;
  }
  const [app, a, f] = await Promise.all([import(`${FB}/firebase-app.js`), import(`${FB}/firebase-auth.js`), import(`${FB}/firebase-firestore.js`)]);
  fb = { ...a, ...f };
  const fapp = app.initializeApp(cfg.firebase);
  auth = a.getAuth(fapp); db = f.getFirestore(fapp);
  if (cfg.emulator){ a.connectAuthEmulator(auth, "http://127.0.0.1:9099", { disableWarnings: true }); f.connectFirestoreEmulator(db, "127.0.0.1", 8085); }
  await loadMeta();
  // sign-in, sign-out and first-time setup buttons can appear on any screen
  root.addEventListener("click", async e => {
    const b = e.target.closest("[data-act]"); if (!b) return;
    if (b.dataset.act === "signin") signIn();
    if (b.dataset.act === "signout") fb.signOut(auth);
    if (b.dataset.act === "seed" && isAdmin()){
      try { const batch = fb.writeBatch(db); DEFAULT_CATS.forEach(([id, name], i) => batch.set(fb.doc(db, "categories", id), { name, order: i + 1 }));
        await batch.commit(); await loadMeta(); toast("הקטגוריות נוצרו."); route(); } catch(err){ fail(err); }
    }
  });
  a.onAuthStateChanged(auth, async u => {
    S.user = u; S.profile = null;
    if (u){ const p = await fb.getDoc(fb.doc(db, "users", u.uid)); S.profile = p.exists() ? { id: u.uid, ...p.data() } : null; }
    S.ready = true; route();
  });
  window.addEventListener("hashchange", () => { if (location.hash.startsWith("#forum")) route(); });
}

async function loadMeta(){
  const [s, c] = await Promise.all([fb.getDoc(fb.doc(db, "settings", "forum")), fb.getDocs(fb.collection(db, "categories"))]);
  if (s.exists()) S.settings = { moderation: true, rules: "", ...s.data() };
  S.cats = c.docs.map(d => ({ id: d.id, ...d.data() })).sort((a, b) => (a.order ?? 99) - (b.order ?? 99));
}

// ---------- layout ----------
function resetHandlers(){ root.onclick = root.onchange = root.onsubmit = root.oninput = null; }
function shell(inner, crumbs = []){
  resetHandlers();
  const u = S.user, p = S.profile;
  const who = !u ? `<button type="button" class="fm-btn primary" data-act="signin">התחברות עם Google</button>`
    : !p ? "" : `<div class="fm-user"><a href="#forum/me" class="fm-me">${avatar(p)}<span>${esc(p.name)}</span>${ROLE[p.role] ? `<em class="fm-role ${p.role}">${ROLE[p.role]}</em>` : ""}</a>
      ${isMod() ? `<a class="fm-btn" href="#forum/admin">ניהול${S.pendingCount ? ` <b class="fm-count">${S.pendingCount}</b>` : ""}</a>` : ""}
      <button type="button" class="fm-btn ghost" data-act="signout">התנתקות</button></div>`;
  root.innerHTML = `<div class="fm">
    <header class="fm-head"><div><nav class="fm-crumbs" aria-label="מיקום בפורום"><a href="#forum">פורום</a>${crumbs.map(c => ` <span aria-hidden="true">‹</span> ${c}`).join("")}</nav>
      <h2 class="fm-title">פורום בית המדרש</h2></div>${who}</header>
    ${S.profile?.banned ? `<p class="fm-banner bad">החשבון שלכם חסום לכתיבה בפורום. אפשר עדיין לקרוא.</p>` : ""}
    ${inner}</div>`;
}
const avatar = p => p?.photo ? `<img class="fm-av" src="${esc(p.photo)}" alt="" referrerpolicy="no-referrer">` : `<span class="fm-av ph" aria-hidden="true">${esc((p?.name || p?.author || "?").trim()[0] || "?")}</span>`;
const badges = t => [t.pinned && `<em class="fm-badge pin">נעוץ</em>`, t.locked && `<em class="fm-badge lock">נעול</em>`, t.status === "pending" && `<em class="fm-badge wait">ממתין לאישור</em>`].filter(Boolean).join("");

// ---------- routing ----------
async function route(){
  if (!root || !S.ready) return;
  const parts = location.hash.replace(/^#forum\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (S.user && !S.profile) return viewProfileSetup();
  try {
    if (isMod()) countPending();
    if (parts[0] === "t" && parts[1]) return await viewThread(parts[1]);
    if (parts[0] === "new") return viewNew(parts[1]);
    if (parts[0] === "admin") return isMod() ? await viewAdmin(parts[1] || "queue") : go("#forum");
    if (parts[0] === "me") return S.profile ? viewMe() : go("#forum");
    return await viewHome(parts[0] === "c" ? parts[1] : "");
  } catch(e){ fail(e); }
  finally { window.scrollTo({ top: 0 }); }
}

async function countPending(){
  try {
    const [a, b] = await Promise.all([
      fb.getCountFromServer(fb.query(fb.collection(db, "threads"), fb.where("status", "==", "pending"))),
      fb.getCountFromServer(fb.query(fb.collection(db, "posts"), fb.where("status", "==", "pending")))]);
    const n = a.data().count + b.data().count;
    if (n !== S.pendingCount){ S.pendingCount = n; const el = root.querySelector('.fm-user a[href="#forum/admin"]'); if (el) el.innerHTML = `ניהול${n ? ` <b class="fm-count">${n}</b>` : ""}`; }
  } catch(e){}
}

// ---------- home: categories and threads ----------
async function viewHome(cat){
  const col = fb.collection(db, "threads");
  const pub = cat ? fb.query(col, fb.where("cat", "==", cat), fb.where("status", "==", "ok")) : fb.query(col, fb.where("status", "==", "ok"));
  const qs = [fb.getDocs(pub)];
  if (S.user) qs.push(fb.getDocs(fb.query(col, fb.where("uid", "==", S.user.uid), fb.where("status", "==", "pending"))));
  if (isMod()) qs.push(fb.getDocs(fb.query(col, fb.where("status", "==", "pending"))));
  const snaps = await Promise.all(qs), seen = new Map();
  snaps.forEach(s => s.docs.forEach(d => seen.set(d.id, { id: d.id, ...d.data() })));
  const list = [...seen.values()].filter(t => !cat || t.cat === cat)
    .sort((a, b) => (b.pinned - a.pinned) || ((b.last?.toMillis?.() ?? Date.now()) - (a.last?.toMillis?.() ?? Date.now())));
  const rules = S.settings.rules || DEFAULT_RULES;
  shell(`
    <details class="fm-rules"${S.user ? "" : " open"}><summary>כללי הפורום</summary><p>${fmtBody(rules)}</p></details>
    <div class="fm-bar">
      <div class="fm-cats" role="list">${[["", "הכול"], ...S.cats.map(c => [c.id, c.name])].map(([id, n]) =>
        `<a role="listitem" class="fm-cat${id === cat ? " on" : ""}" href="${id ? `#forum/c/${encodeURIComponent(id)}` : "#forum"}"${id === cat ? ' aria-current="page"' : ""}>${esc(n)}</a>`).join("")}</div>
      ${S.cats.length ? (canWrite() ? `<a class="fm-btn primary" href="#forum/new${cat ? "/" + encodeURIComponent(cat) : ""}">+ דיון חדש</a>`
        : !S.user ? `<button type="button" class="fm-btn primary" data-act="signin">התחברו כדי לכתוב</button>` : "") : ""}
    </div>
    ${!S.cats.length ? (isAdmin() ? `<div class="fm-empty"><h3>עוד אין קטגוריות</h3><p>צרו את קטגוריות ברירת המחדל, ואפשר לשנות אותן אחר כך בניהול.</p><button type="button" class="fm-btn primary" data-act="seed">יצירת קטגוריות</button></div>`
        : `<div class="fm-empty"><h3>הפורום בהקמה</h3><p>המנהלים מכינים את הקטגוריות.</p></div>`)
      : list.length ? `<ul class="fm-list">${list.map(t => `<li><a class="fm-row" href="#forum/t/${t.id}">
          <span class="fm-row-main"><b>${esc(t.title)}</b>${badges(t)}<small>${esc(catName(t.cat))} · ${esc(t.author)} · ${ago(t.created)}</small></span>
          <span class="fm-row-side"><b>${t.replies || 0}</b><small>תגובות</small><small>${ago(t.last)}</small></span></a></li>`).join("")}</ul>`
      : `<div class="fm-empty"><h3>עוד אין דיונים כאן</h3><p>${canWrite() ? "פתחו את הדיון הראשון." : "התחברו ופתחו את הדיון הראשון."}</p></div>`}`,
    cat ? [esc(catName(cat))] : []);
}

// ---------- a thread ----------
async function viewThread(id){
  const tSnap = await fb.getDoc(fb.doc(db, "threads", id)).catch(() => null);
  if (!tSnap?.exists()){ shell(`<div class="fm-empty"><h3>הדיון לא נמצא</h3><p>ייתכן שנמחק או שעוד לא אושר.</p><a class="fm-btn" href="#forum">לכל הדיונים</a></div>`); return; }
  const t = { id, ...tSnap.data() }, col = fb.collection(db, "posts");
  const qs = [fb.getDocs(fb.query(col, fb.where("thread", "==", id), fb.where("status", "==", "ok")))];
  if (isMod()) qs.push(fb.getDocs(fb.query(col, fb.where("thread", "==", id))));
  else if (S.user) qs.push(fb.getDocs(fb.query(col, fb.where("thread", "==", id), fb.where("uid", "==", S.user.uid))));
  const seen = new Map();
  (await Promise.all(qs)).forEach(s => s.docs.forEach(d => seen.set(d.id, { id: d.id, ...d.data() })));
  const posts = [...seen.values()].sort((a, b) => (a.created?.toMillis?.() ?? Date.now()) - (b.created?.toMillis?.() ?? Date.now()));
  const uids = [...new Set([t.uid, ...posts.map(p => p.uid)])];
  const people = Object.fromEntries((await Promise.all(uids.map(u => fb.getDoc(fb.doc(db, "users", u))))).map(s => [s.id, s.exists() ? s.data() : null]));
  const mine = x => S.user && x.uid === S.user.uid;
  const card = (x, isThread) => {
    const p = people[x.uid] || { name: x.author }, kind = isThread ? "thread" : "post";
    const acts = [
      isMod() && x.status === "pending" && `<button type="button" class="fm-btn small ok" data-act="approve-${kind}" data-id="${x.id}">אישור</button>`,
      (mine(x) && canWrite() && !(isThread && t.locked)) && `<button type="button" class="fm-btn small ghost" data-act="edit-${kind}" data-id="${x.id}">עריכה</button>`,
      (isMod() || (mine(x) && (!isThread || !t.replies))) && `<button type="button" class="fm-btn small ghost" data-act="del-${kind}" data-id="${x.id}">מחיקה</button>`,
      (canWrite() && !mine(x)) && `<button type="button" class="fm-btn small ghost" data-act="report" data-id="${isThread ? "" : x.id}">דיווח</button>`,
      (isMod() && !mine(x) && p.role === "user") && `<button type="button" class="fm-btn small ghost" data-act="ban" data-uid="${x.uid}" data-ban="${p.banned ? 0 : 1}">${p.banned ? "ביטול חסימה" : "חסימת המשתמש"}</button>`,
    ].filter(Boolean).join("");
    return `<article class="fm-post${x.status === "pending" ? " pending" : ""}" id="p-${x.id}">
      <header>${avatar({ ...p, author: x.author })}<div><b>${esc(p.name || x.author)}</b>${ROLE[p.role] ? `<em class="fm-role ${p.role}">${ROLE[p.role]}</em>` : ""}
        <small>${ago(x.created)}${x.edited ? " · נערך" : ""}</small></div>${x.status === "pending" ? `<em class="fm-badge wait">ממתין לאישור</em>` : ""}</header>
      <div class="fm-body" data-body="${x.id}">${fmtBody(x.body)}</div>${acts ? `<footer>${acts}</footer>` : ""}</article>`;
  };
  const modBar = isMod() ? `<div class="fm-modbar" role="group" aria-label="כלי ניהול">
      <button type="button" class="fm-btn small" data-act="pin">${t.pinned ? "ביטול נעיצה" : "נעיצה למעלה"}</button>
      <button type="button" class="fm-btn small" data-act="lock">${t.locked ? "פתיחת הדיון" : "נעילת הדיון"}</button>
      <label>קטגוריה <select data-act="move">${S.cats.map(c => `<option value="${esc(c.id)}"${c.id === t.cat ? " selected" : ""}>${esc(c.name)}</option>`).join("")}</select></label></div>` : "";
  const compose = !S.user ? `<p class="fm-note"><button type="button" class="fm-btn primary" data-act="signin">התחברו כדי להגיב</button></p>`
    : t.locked ? `<p class="fm-note">הדיון נעול לתגובות.</p>`
    : t.status !== "ok" ? `<p class="fm-note">אפשר להגיב אחרי שהדיון יאושר.</p>`
    : !canWrite() ? "" : `<form class="fm-form" data-form="reply"><label for="fmReply">תגובה</label>
        <textarea id="fmReply" name="body" rows="5" maxlength="10000" required></textarea>
        <div class="fm-form-foot">${S.settings.moderation && !isMod() ? `<small>התגובה תפורסם אחרי אישור מנהל.</small>` : "<span></span>"}<button class="fm-btn primary">שליחה</button></div></form>`;
  shell(`<div class="fm-thread"><h3 class="fm-th-title">${esc(t.title)} ${badges(t)}</h3>${modBar}
    ${card(t, true)}<h4 class="fm-replies">${posts.length ? `${posts.length} תגובות` : "עוד אין תגובות"}</h4>${posts.map(p => card(p, false)).join("")}${compose}</div>`,
    [`<a href="#forum/c/${encodeURIComponent(t.cat)}">${esc(catName(t.cat))}</a>`]);
  root.onclick = e => threadAction(e, t, posts);
  root.onchange = e => { if (e.target.dataset.act === "move") upd(fb.doc(db, "threads", t.id), { cat: e.target.value }, "הדיון הועבר."); };
  root.onsubmit = async e => {
    e.preventDefault();
    const body = e.target.body.value.trim(); if (!body) return;
    const status = S.settings.moderation && !isMod() ? "pending" : "ok";
    const b = fb.writeBatch(db);
    b.set(fb.doc(fb.collection(db, "posts")), { thread: t.id, body, uid: S.user.uid, author: S.profile.name, created: fb.serverTimestamp(), status });
    if (status === "ok") b.update(fb.doc(db, "threads", t.id), { replies: fb.increment(1), last: fb.serverTimestamp() });
    try { await b.commit(); toast(status === "ok" ? "התגובה פורסמה." : "התגובה נשלחה ותפורסם אחרי אישור."); route(); } catch(err){ fail(err); }
  };
}

async function upd(ref, data, msg){ try { await fb.updateDoc(ref, data); if (msg) toast(msg); route(); } catch(e){ fail(e); } }

async function threadAction(e, t, posts){
  const b = e.target.closest("[data-act]"); if (!b || b.tagName === "SELECT") return;
  const act = b.dataset.act, id = b.dataset.id, tRef = fb.doc(db, "threads", t.id);
  if (act === "pin") return upd(tRef, { pinned: !t.pinned }, t.pinned ? "הנעיצה בוטלה." : "הדיון ננעץ למעלה.");
  if (act === "lock") return upd(tRef, { locked: !t.locked }, t.locked ? "הדיון נפתח." : "הדיון ננעל.");
  if (act === "approve-thread") return upd(tRef, { status: "ok", last: fb.serverTimestamp() }, "הדיון אושר ופורסם.");
  if (act === "approve-post"){
    const batch = fb.writeBatch(db);
    batch.update(fb.doc(db, "posts", id), { status: "ok" });
    batch.update(tRef, { replies: fb.increment(1), last: fb.serverTimestamp() });
    try { await batch.commit(); toast("התגובה אושרה."); route(); } catch(err){ fail(err); } return;
  }
  if (act === "del-thread"){
    if (!await confirmBox("למחוק את הדיון וכל התגובות שבו?")) return;
    try {
      const batch = fb.writeBatch(db);
      posts.forEach(p => batch.delete(fb.doc(db, "posts", p.id)));
      if (isMod()) (await fb.getDocs(fb.query(fb.collection(db, "posts"), fb.where("thread", "==", t.id)))).docs.forEach(d => batch.delete(d.ref));
      batch.delete(tRef); await batch.commit(); toast("הדיון נמחק."); go("#forum");
    } catch(err){ fail(err); } return;
  }
  if (act === "del-post"){
    if (!await confirmBox("למחוק את התגובה?")) return;
    const p = posts.find(x => x.id === id), batch = fb.writeBatch(db);
    batch.delete(fb.doc(db, "posts", id));
    if (isMod() && p?.status === "ok") batch.update(tRef, { replies: fb.increment(-1) });
    try { await batch.commit(); toast("התגובה נמחקה."); route(); } catch(err){ fail(err); } return;
  }
  if (act === "edit-thread" || act === "edit-post") return editInline(act === "edit-thread" ? t : posts.find(x => x.id === id), act === "edit-thread");
  if (act === "report"){
    const reason = await promptBox("מה הבעיה בהודעה הזו?", "למשל: מידע מבצעי, לשון הרע, פרסום");
    if (!reason) return;
    try { await fb.addDoc(fb.collection(db, "reports"), { thread: t.id, post: id || "", reason, uid: S.user.uid, created: fb.serverTimestamp() }); toast("תודה, הדיווח נשלח למנהלים."); } catch(err){ fail(err); }
    return;
  }
  if (act === "ban") return upd(fb.doc(db, "users", b.dataset.uid), { banned: b.dataset.ban === "1" }, b.dataset.ban === "1" ? "המשתמש נחסם." : "החסימה בוטלה.");
}

function editInline(x, isThread){
  const box = root.querySelector(`[data-body="${x.id}"]`);
  box.innerHTML = `<form class="fm-form" data-edit>${isThread ? `<label>כותרת<input name="title" maxlength="150" required value="${esc(x.title)}"></label>` : ""}
    <textarea name="body" rows="6" maxlength="10000" required>${esc(x.body)}</textarea>
    <div class="fm-form-foot"><button type="button" class="fm-btn ghost" data-cancel>ביטול</button><button class="fm-btn primary">שמירה</button></div></form>`;
  const f = box.querySelector("form");
  f.querySelector("[data-cancel]").onclick = ev => { ev.stopPropagation(); route(); };
  f.onsubmit = ev => {
    ev.preventDefault(); ev.stopPropagation();
    const data = { body: f.body.value.trim(), edited: fb.serverTimestamp() };
    if (isThread) data.title = f.title.value.trim();
    upd(fb.doc(db, isThread ? "threads" : "posts", x.id), data, "נשמר.");
  };
}

// ---------- new thread ----------
function viewNew(cat){
  if (!canWrite()) return go("#forum");
  shell(`<form class="fm-form fm-new" data-form="new">
    <label>קטגוריה<select name="cat" required>${S.cats.map(c => `<option value="${esc(c.id)}"${c.id === cat ? " selected" : ""}>${esc(c.name)}</option>`).join("")}</select></label>
    <label>כותרת<input name="title" maxlength="150" minlength="3" required placeholder="במה הדיון?"></label>
    <label>תוכן<textarea name="body" rows="9" maxlength="10000" required></textarea></label>
    <p class="fm-banner">לפני שליחה: לא לכתוב שמות יחידות, מיקומים, פעילויות מבצעיות או כל מידע מסווג.</p>
    <div class="fm-form-foot">${S.settings.moderation && !isMod() ? `<small>הדיון יפורסם אחרי אישור מנהל.</small>` : "<span></span>"}<button class="fm-btn primary">פרסום</button></div></form>`, ["דיון חדש"]);
  root.onsubmit = async e => {
    e.preventDefault();
    const f = e.target, status = S.settings.moderation && !isMod() ? "pending" : "ok";
    try {
      const ref = await fb.addDoc(fb.collection(db, "threads"), { cat: f.cat.value, title: f.title.value.trim(), body: f.body.value.trim(), uid: S.user.uid,
        author: S.profile.name, created: fb.serverTimestamp(), last: fb.serverTimestamp(), replies: 0, status, pinned: false, locked: false });
      toast(status === "ok" ? "הדיון פורסם." : "הדיון נשלח ויפורסם אחרי אישור מנהל.");
      go(`#forum/t/${ref.id}`);
    } catch(err){ fail(err); }
  };
}

// ---------- profile ----------
function viewProfileSetup(){
  const name = (S.user.displayName || "").slice(0, 40);
  resetHandlers();
  root.innerHTML = `<div class="fm"><form class="fm-form fm-new" data-form="setup"><h2 class="fm-title">ברוכים הבאים לפורום</h2>
    <p>בחרו שם שיוצג ליד ההודעות שלכם. לא חייב להיות השם המלא.</p>
    <label>שם תצוגה<input name="name" minlength="2" maxlength="40" required value="${esc(name)}"></label>
    <p class="fm-banner">${fmtBody(S.settings.rules || DEFAULT_RULES)}</p>
    <label class="fm-check"><input type="checkbox" name="agree" required> קראתי ואני מסכים לכללי הפורום</label>
    <div class="fm-form-foot"><button type="button" class="fm-btn ghost" data-out>ביטול</button><button class="fm-btn primary">כניסה לפורום</button></div></form></div>`;
  root.querySelector("[data-out]").onclick = () => fb.signOut(auth);
  root.onsubmit = async e => {
    e.preventDefault();
    const owner = cfg.ownerEmail && S.user.email === cfg.ownerEmail && (S.user.emailVerified || cfg.emulator);
    const p = { name: e.target.name.value.trim(), photo: S.user.photoURL || "", role: owner ? "admin" : "user", banned: false, created: fb.serverTimestamp() };
    try { await fb.setDoc(fb.doc(db, "users", S.user.uid), p); S.profile = { id: S.user.uid, ...p }; toast("נרשמתם לפורום."); route(); } catch(err){ fail(err); }
  };
}

function viewMe(){
  shell(`<form class="fm-form fm-new" data-form="me"><label>שם תצוגה<input name="name" minlength="2" maxlength="40" required value="${esc(S.profile.name)}"></label>
    <div class="fm-form-foot"><span></span><button class="fm-btn primary">שמירה</button></div></form>`, ["הפרופיל שלי"]);
  root.onsubmit = async e => {
    e.preventDefault(); const name = e.target.name.value.trim();
    try { await fb.updateDoc(fb.doc(db, "users", S.user.uid), { name }); S.profile.name = name; toast("השם עודכן. הודעות חדשות יופיעו בשם הזה."); route(); } catch(err){ fail(err); }
  };
}

// ---------- moderation ----------
async function viewAdmin(tab){
  const tabs = [["queue", "ממתינים לאישור"], ["reports", "דיווחים"], ["users", "משתמשים"], ...(isAdmin() ? [["settings", "הגדרות וקטגוריות"]] : [])];
  let body = "";
  if (tab === "queue"){
    const [th, po] = await Promise.all([fb.getDocs(fb.query(fb.collection(db, "threads"), fb.where("status", "==", "pending"))),
      fb.getDocs(fb.query(fb.collection(db, "posts"), fb.where("status", "==", "pending")))]);
    const items = [...th.docs.map(d => ({ kind: "thread", id: d.id, ...d.data() })), ...po.docs.map(d => ({ kind: "post", id: d.id, ...d.data() }))]
      .sort((a, b) => (a.created?.toMillis?.() ?? 0) - (b.created?.toMillis?.() ?? 0));
    body = items.length ? `<ul class="fm-queue">${items.map(x => `<li class="fm-post pending"><header><div><b>${x.kind === "thread" ? "דיון חדש: " + esc(x.title) : "תגובה"}</b>
        <small>${esc(x.author)} · ${ago(x.created)} · <a href="#forum/t/${x.kind === "thread" ? x.id : x.thread}">לדיון</a></small></div></header>
        <div class="fm-body">${fmtBody(x.body.length > 600 ? x.body.slice(0, 600) + "…" : x.body)}</div>
        <footer><button type="button" class="fm-btn small ok" data-q="ok" data-kind="${x.kind}" data-id="${x.id}" data-thread="${esc(x.thread || "")}">אישור</button>
        <button type="button" class="fm-btn small ghost" data-q="del" data-kind="${x.kind}" data-id="${x.id}">מחיקה</button></footer></li>`).join("")}</ul>`
      : `<div class="fm-empty"><h3>אין הודעות שממתינות לאישור</h3></div>`;
  } else if (tab === "reports"){
    const r = await fb.getDocs(fb.collection(db, "reports"));
    const items = r.docs.map(d => ({ id: d.id, ...d.data() }));
    body = items.length ? `<ul class="fm-queue">${items.map(x => `<li class="fm-post"><div class="fm-body"><b>${esc(x.reason)}</b></div>
        <footer><a class="fm-btn small" href="#forum/t/${esc(x.thread)}">לדיון</a><button type="button" class="fm-btn small ghost" data-rep="${x.id}">סגירת הדיווח</button></footer></li>`).join("")}</ul>`
      : `<div class="fm-empty"><h3>אין דיווחים פתוחים</h3></div>`;
  } else if (tab === "users"){
    const u = await fb.getDocs(fb.collection(db, "users"));
    const users = u.docs.map(d => ({ id: d.id, ...d.data() })).sort((a, b) => (a.role === b.role ? a.name.localeCompare(b.name, "he") : a.role === "admin" ? -1 : b.role === "admin" ? 1 : a.role === "mod" ? -1 : 1));
    body = `<label class="fm-search">חיפוש משתמש <input type="search" data-filter placeholder="שם"></label>
      <table class="fm-users"><thead><tr><th>שם</th><th>תפקיד</th><th>מצב</th></tr></thead><tbody>${users.map(x => `<tr data-name="${esc(x.name)}">
        <th scope="row">${avatar(x)} ${esc(x.name)}</th>
        <td>${isAdmin() && x.id !== S.user.uid ? `<select data-role="${x.id}" aria-label="תפקיד של ${esc(x.name)}">${["user", "mod", "admin"].map(r => `<option value="${r}"${x.role === r ? " selected" : ""}>${{ user: "משתמש", mod: "מנהל", admin: "מנהל ראשי" }[r]}</option>`).join("")}</select>` : esc(ROLE[x.role] || "משתמש")}</td>
        <td>${x.id !== S.user.uid && (isAdmin() || x.role === "user") ? `<button type="button" class="fm-btn small ${x.banned ? "ok" : "ghost"}" data-banuser="${x.id}" data-ban="${x.banned ? 0 : 1}">${x.banned ? "ביטול חסימה" : "חסימה"}</button>` : (x.banned ? "חסום" : "פעיל")}</td></tr>`).join("")}</tbody></table>`;
  } else if (tab === "settings" && isAdmin()){
    body = `<form class="fm-form fm-new" data-form="settings">
      <label class="fm-check"><input type="checkbox" name="moderation"${S.settings.moderation ? " checked" : ""}> אישור מנהל לפני פרסום של כל דיון ותגובה</label>
      <label>כללי הפורום<textarea name="rules" rows="6">${esc(S.settings.rules || DEFAULT_RULES)}</textarea></label>
      <div class="fm-form-foot"><span></span><button class="fm-btn primary">שמירת הגדרות</button></div></form>
      <h3 class="fm-sub">קטגוריות</h3>
      <ul class="fm-catedit">${S.cats.map(c => `<li><input value="${esc(c.name)}" data-catname="${esc(c.id)}" aria-label="שם הקטגוריה"><input type="number" value="${c.order ?? 0}" data-catorder="${esc(c.id)}" aria-label="סדר" class="fm-num">
        <button type="button" class="fm-btn small ghost" data-catdel="${esc(c.id)}">מחיקה</button></li>`).join("")}</ul>
      <form class="fm-form fm-inline" data-form="addcat"><input name="name" required minlength="2" placeholder="קטגוריה חדשה"><button class="fm-btn">הוספה</button></form>`;
  }
  shell(`<div class="fm-tabs" role="tablist">${tabs.map(([k, n]) => `<a role="tab" href="#forum/admin/${k}" aria-selected="${k === tab}" class="fm-tab${k === tab ? " on" : ""}">${n}</a>`).join("")}</div>${body}`, ["ניהול"]);
  root.onclick = async e => {
    const b = e.target.closest("button"); if (!b) return;
    try {
      if (b.dataset.q){
        const ref = fb.doc(db, b.dataset.kind === "thread" ? "threads" : "posts", b.dataset.id);
        if (b.dataset.q === "del"){ if (!await confirmBox("למחוק את ההודעה?")) return; await fb.deleteDoc(ref); toast("נמחק."); }
        else {
          const batch = fb.writeBatch(db);
          batch.update(ref, b.dataset.kind === "thread" ? { status: "ok", last: fb.serverTimestamp() } : { status: "ok" });
          if (b.dataset.kind === "post") batch.update(fb.doc(db, "threads", b.dataset.thread), { replies: fb.increment(1), last: fb.serverTimestamp() });
          await batch.commit(); toast("אושר ופורסם.");
        }
      }
      if (b.dataset.rep){ await fb.deleteDoc(fb.doc(db, "reports", b.dataset.rep)); toast("הדיווח נסגר."); }
      if (b.dataset.banuser){ await fb.updateDoc(fb.doc(db, "users", b.dataset.banuser), { banned: b.dataset.ban === "1" }); toast(b.dataset.ban === "1" ? "המשתמש נחסם." : "החסימה בוטלה."); }
      if (b.dataset.catdel){ if (!await confirmBox("למחוק את הקטגוריה? דיונים שבה יישארו בלי קטגוריה.")) return; await fb.deleteDoc(fb.doc(db, "categories", b.dataset.catdel)); await loadMeta(); toast("הקטגוריה נמחקה."); }
      route();
    } catch(err){ fail(err); }
  };
  root.onchange = async e => {
    const el = e.target;
    try {
      if (el.dataset.role){ await fb.updateDoc(fb.doc(db, "users", el.dataset.role), { role: el.value }); toast("התפקיד עודכן."); }
      if (el.dataset.catname){ await fb.updateDoc(fb.doc(db, "categories", el.dataset.catname), { name: el.value.trim() }); await loadMeta(); toast("נשמר."); }
      if (el.dataset.catorder){ await fb.updateDoc(fb.doc(db, "categories", el.dataset.catorder), { order: +el.value }); await loadMeta(); toast("נשמר."); }
    } catch(err){ fail(err); }
  };
  root.oninput = e => { if (e.target.dataset.filter != null){ const q = e.target.value.trim(); root.querySelectorAll(".fm-users tbody tr").forEach(r => r.hidden = q && !r.dataset.name.includes(q)); } };
  root.onsubmit = async e => {
    e.preventDefault(); const f = e.target;
    try {
      if (f.dataset.form === "settings"){ const s = { moderation: f.moderation.checked, rules: f.rules.value.trim() }; await fb.setDoc(fb.doc(db, "settings", "forum"), s); S.settings = s; toast("ההגדרות נשמרו."); }
      if (f.dataset.form === "addcat"){
        const name = f.name.value.trim(), id = "c" + Date.now().toString(36);
        await fb.setDoc(fb.doc(db, "categories", id), { name, order: S.cats.length + 1 }); await loadMeta(); toast("הקטגוריה נוספה.");
      }
      route();
    } catch(err){ fail(err); }
  };
}

async function signIn(){
  try {
    if (cfg.emulator){ // local testing only
      const email = await promptBox("אימייל לבדיקה", "owner@test.com"); if (!email) return;
      await fb.signInWithEmailAndPassword(auth, email, "test1234").catch(() => fb.createUserWithEmailAndPassword(auth, email, "test1234"));
      return;
    }
    await fb.signInWithPopup(auth, new fb.GoogleAuthProvider());
  } catch(e){ if (e.code !== "auth/popup-closed-by-user" && e.code !== "auth/cancelled-popup-request") fail(e); }
}

// small in-page dialogs (native confirm/prompt are blocked in some embedded views)
function dialog(html){
  return new Promise(res => {
    const d = document.createElement("dialog"); d.className = "fm-dialog"; d.innerHTML = html; document.body.appendChild(d);
    const done = v => { d.close(); d.remove(); res(v); };
    d.querySelector("[data-no]").onclick = () => done(null);
    d.querySelector("form").onsubmit = ev => { ev.preventDefault(); const i = d.querySelector("input"); done(i ? i.value.trim() : true); };
    d.addEventListener("cancel", () => done(null));
    d.showModal(); (d.querySelector("input") || d.querySelector("button.primary")).focus();
  });
}
const confirmBox = msg => dialog(`<form><p>${esc(msg)}</p><div class="fm-form-foot"><button type="button" class="fm-btn ghost" data-no>ביטול</button><button class="fm-btn primary">כן</button></div></form>`);
const promptBox = (msg, ph) => dialog(`<form><label>${esc(msg)}<input required placeholder="${esc(ph || "")}"></label><div class="fm-form-foot"><button type="button" class="fm-btn ghost" data-no>ביטול</button><button class="fm-btn primary">שליחה</button></div></form>`);
