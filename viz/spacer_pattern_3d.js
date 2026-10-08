// SADP · SAQP 3D 공통 엔진 (Three.js r128). 페이지에서 window.SP_MODE = "sadp" | "saqp" 를 정한 뒤 불러온다.
// 모든 구조는 위에서 본 발자국(x–z 직사각형)을 y 방향으로 세운 상자로 그린다. 선은 z 방향으로 길다.
(() => {
const MODE = window.SP_MODE;
const P0 = 80, MC = [-80, 0, 80];          // 초기(노광) 피치와 맨드릴 중심
const L = 50, ZT = 40, XV = 124, ZV = 80;  // 맨드릴 반길이, 트림 후 남길 범위, 보이는 영역
const COL = { sub:0xcbd5e1, tgt:0x93c5fd, hm:0x94a3b8, m1:0xfdba74, m2:0xfcd34d, sp1:0xa78bfa, sp2:0xf472b6,
  res:0x86efac, resid:0x6d28d9, bridge:0xef4444, cut:0xef4444, sCore:0xf97316, sGap:0x2563eb, sG:0x16a34a };
const SPACE = MODE === "sadp"
  ? { core:["코어", "sCore", "맨드릴 자리"], gap:["갭", "sGap", "스페이서 사이"] }
  : { a:["α", "sCore", "맨드릴 2 자리"], b:["β", "sGap", "맨드릴 1 자리"], g:["γ", "sG", "맨드릴 1 사이"] };
// 층 높이 (그림 단위 ≈ nm)
const Y = MODE === "sadp"
  ? { TG0:0, TG1:10, HM0:10, HM1:14, M10:14, M11:34, RS:6 }
  : { TG0:0, TG1:8, HM0:8, HM1:11, M20:11, M21:25, M10:25, M11:39, RS:5 };
const NSTEP = MODE === "sadp" ? 7 : 9;
const ST = MODE === "sadp"
  ? { m1:1, dep:2, eb:3, pull1:4, xfer:5, cut:6 }
  : { m1:1, sp1:2, pull1:3, xm2:4, sp2:5, pull2:6, xfer:7, cut:8 };

const state = { step:0, dc:0, dt:0, eb:0, pull:0, sec:false, top:false };
const anim = { s:0 };

// ---------- 발자국 도구 ----------
const R = (x0, x1, z0, z1) => ({ x0, x1, z0, z1 });
function ringFp(r) {
  const { x0, x1, z0, z1, w } = r;
  if (w <= .05 || x1 - x0 <= .05 || z1 - z0 <= .05) return [];
  if (2 * w >= x1 - x0 - .05) return [R(x0, x1, z0, z1)];
  return [R(x0, x0 + w, z0, z1), R(x1 - w, x1, z0, z1), R(x0 + w, x1 - w, z0, z0 + w), R(x0 + w, x1 - w, z1 - w, z1)];
}
const thinR = (r, th) => ({ x0:r.x0 + th, x1:r.x1 - th, z0:r.z0 + th, z1:r.z1 - th, w:Math.max(.3, r.w - 2 * th) });
const grow = (r, d) => R(r.x0 - d, r.x1 + d, r.z0 - d, r.z1 + d);
function sub1(a, b) {
  if (b.x1 <= a.x0 || b.x0 >= a.x1 || b.z1 <= a.z0 || b.z0 >= a.z1) return [a];
  const out = [], x0 = Math.max(a.x0, b.x0), x1 = Math.min(a.x1, b.x1);
  if (b.x0 > a.x0) out.push(R(a.x0, b.x0, a.z0, a.z1));
  if (b.x1 < a.x1) out.push(R(b.x1, a.x1, a.z0, a.z1));
  if (b.z0 > a.z0) out.push(R(x0, x1, a.z0, b.z0));
  if (b.z1 < a.z1) out.push(R(x0, x1, b.z1, a.z1));
  return out;
}
const subtract = (list, b) => list.flatMap(a => sub1(a, b));
const subtractAll = (list, bs) => bs.reduce((acc, b) => subtract(acc, b), list);
const FULL = R(-XV, XV, -ZV, ZV);
const clamp = v => Math.max(0, Math.min(1, v));

// ---------- 치수 ----------
function params(pullFrac1 = 1, pullFrac2 = 1) {
  const thin = state.pull ? (MODE === "sadp" ? 2.5 : 1.5) : 0;
  if (MODE === "sadp") {
    const C = 20 + state.dc, t = 20 + state.dt;
    const mand = MC.map(m => R(m - C / 2, m + C / 2, -L, L));
    const sp = MC.map(m => ({ x0:m - C / 2 - t, x1:m + C / 2 + t, z0:-L - t, z1:L + t, w:t }));
    const fin = sp.map(r => thinR(r, thin * pullFrac1));
    return { C, t, thin, mand, sp, fin };
  }
  const C1 = 30 + state.dc, t1 = 10 + state.dt, t2 = 10;
  const mand = MC.map(m => R(m - C1 / 2, m + C1 / 2, -L, L));
  const sp1 = MC.map(m => ({ x0:m - C1 / 2 - t1, x1:m + C1 / 2 + t1, z0:-L - t1, z1:L + t1, w:t1 }));
  const m2 = sp1.map(r => thinR(r, thin * pullFrac1));
  const sp2 = [];
  m2.forEach(r => {
    sp2.push({ x0:r.x0 - t2, x1:r.x1 + t2, z0:r.z0 - t2, z1:r.z1 + t2, w:t2 });
    const h = { x0:r.x0 + r.w, x1:r.x1 - r.w, z0:r.z0 + r.w, z1:r.z1 - r.w };
    if (h.x1 - h.x0 > .2) sp2.push({ ...h, w:Math.min(t2, (h.x1 - h.x0) / 2) });
  });
  const fin = sp2.map(r => thinR(r, thin * pullFrac2));
  return { C1, t1, t2, thin, mand, sp1, m2, sp2, fin };
}

// 위에서 본 긴 다리(직선부)만 x 순으로
const legs = rings => rings.flatMap(ringFp).filter(p => p.z1 - p.z0 > 2 * ZT && p.z0 < 0 && p.z1 > 0).sort((a, b) => a.x0 - b.x0);

function classify(c, p) {
  if (MODE === "sadp") return p.mand.some(m => c > m.x0 && c < m.x1) ? "core" : "gap";
  if (legs(p.m2).some(l => c > l.x0 && c < l.x1)) return "a";
  if (p.mand.some(m => c > m.x0 && c < m.x1)) return "b";
  return "g";
}
function spaces(p) {
  const ls = legs(p.fin), out = [];
  for (let i = 0; i + 1 < ls.length; i++) {
    const a = ls[i], b = ls[i + 1];
    out.push({ x0:a.x1, x1:b.x0, w:b.x0 - a.x1, cls:classify((a.x1 + b.x0) / 2, p) });
  }
  return { ls, sp:out };
}
function cutRegions(p) {
  const ls = legs(p.fin);
  const pick = MODE === "sadp" ? [[1, 8, 20], [4, -24, -12]] : [[2, 10, 22], [6, -20, -8], [9, 14, 26]];
  return [R(-XV, XV, ZT, ZV), R(-XV, XV, -ZV, -ZT),
    ...pick.filter(([i]) => ls[i]).map(([i, z0, z1]) => R(ls[i].x0 - 3, ls[i].x1 + 3, z0, z1))];
}

// ---------- 그리기 목록 만들기 ----------
function build() {
  const B = [], f = k => clamp(anim.s - (k - 1));
  const add = (fps, y0, y1, c, o = {}) => { if (y1 - y0 > .02) fps.forEach(r => B.push({ ...r, y0, y1, c, ...o })); };
  add([FULL], -14, 0, "sub");

  // 맨드릴 층 (식각 → 남은 기둥 → 제거)
  function mandLayer(pieces, y0, y1, fEtch, fPull, c, resist) {
    const h = y1 - y0;
    if (fEtch < .999) add([FULL], y0, y0 + h * (1 - fEtch), c);
    if (fEtch > .001) add(pieces, y0, y0 + h * (1 - fPull), c);
    if (resist && fEtch < .999) add(pieces, y1, y1 + Y.RS * (1 - fEtch), "res");
  }
  // 스페이서 (등각 증착 → 에치백 → 맨드릴 제거 때 얇아짐 → 전사 때 소모)
  function spacerStage(o) {
    const { pieces, walls, y0, y1, t, fDep, fEb, fPull, thinMax, consume, c, final } = o;
    const tt = t * fDep;
    if (fDep <= .01 || consume >= .999) return;
    const floorArea = subtractAll([FULL], pieces);
    if (fEb <= .001) {                       // 증착 중: 맨드릴을 감싼 막 + 바닥 막
      add(pieces.map(r => grow(r, tt)), y0, y1 + tt, c);
      add(floorArea, y0, y0 + tt, c);
      return;
    }
    const eb = final ? state.eb : 0;
    const capTh = tt * (1 - fEb);
    const floorTh = eb === 1 ? Math.max(capTh, 3) : capTh;
    let top = y1 - (eb === 2 ? .45 * (y1 - y0) * fEb : 0) - (state.pull ? .15 * (y1 - y0) * fPull : 0);
    top = y0 + (top - y0) * (1 - consume);
    add(walls.map(r => thinR(r, thinMax * fPull)).flatMap(ringFp), y0, top, c);
    if (capTh > .05 && top >= y1 - .01) add(pieces.map(r => grow(r, tt)), y1, y1 + capTh, c);
    if (floorTh > .05 && consume < .5) add(floorArea, y0, y0 + floorTh, eb === 1 && fEb > .999 ? "resid" : c);
  }
  // 최종 전사 + 트림·컷
  function transfer(p, fT, fC, residueOn) {
    const lines = p.fin.flatMap(ringFp);
    let resid = [];
    if (residueOn) resid = subtractAll(subtractAll([FULL], MODE === "sadp" ? p.mand : p.m2.flatMap(ringFp)), lines);
    const cuts = cutRegions(p);
    const done = fC >= .5;
    const L2 = done ? subtractAll(lines, cuts) : lines, Rs = done ? subtractAll(resid, cuts) : resid;
    const fH = clamp(fT * 2), fG = clamp(fT * 2 - 1);
    const tgTop = Y.TG1 - (state.eb === 2 ? 3 * fG : 0);
    // 대상막
    if (fG < .999) add([FULL], Y.TG0, Y.TG0 + (Y.TG1 - Y.TG0) * (1 - fG), "tgt");
    if (fG > .001) { add(L2, Y.TG0, tgTop, "tgt"); add(Rs, Y.TG0, Y.TG1, "bridge"); }
    // 하드마스크 (컷 단계 후반에 제거)
    if (!done) {
      if (fH < .999) add([FULL], Y.HM0, Y.HM0 + (Y.HM1 - Y.HM0) * (1 - fH), "hm");
      if (fH > .001) add(lines.concat(resid), Y.HM0, Y.HM1, "hm");
    }
    // 공간 색 (전사 끝난 뒤, 직선부)
    if (fT > .95 && state.eb !== 1) {
      spaces(p).sp.forEach(s => { if (s.w > .3) add([R(s.x0, s.x1, -ZT, ZT)], Y.TG0, Y.TG0 + .7, SPACE[s.cls][1], { noEdge:true }); });
    }
    // 컷 마스크 (반투명)
    if (fC > .001 && fC < .999) {
      const op = .4 * (fC < .5 ? fC * 2 : (1 - fC) * 2);
      add(cuts, Y.HM1 + 6, Y.HM1 + 10, "cut", { op, noEdge:true });
    }
    return done;
  }

  if (MODE === "sadp") {
    const pFin = params(1), p = params(f(ST.pull1));
    const fT = f(ST.xfer), fC = f(ST.cut);
    const stripped = transfer(pFin, fT, fC, state.eb === 1 && fT > .001);
    if (!stripped) {
      mandLayer(p.mand, Y.M10, Y.M11, f(ST.m1), f(ST.pull1), "m1", true);
      spacerStage({ pieces:p.mand, walls:p.sp, y0:Y.M10, y1:Y.M11, t:p.t, fDep:f(ST.dep), fEb:f(ST.eb), fPull:f(ST.pull1),
        thinMax:p.thin, consume:fT * (state.eb === 2 ? 1 : .5), c:"sp1", final:true });
    }
  } else {
    const p = params(f(ST.pull1), f(ST.pull2)), pFin = params(1, 1);
    const fT = f(ST.xfer), fC = f(ST.cut);
    const stripped = transfer(pFin, fT, fC, state.eb === 1 && fT > .001);
    if (!stripped) {
      // 맨드릴 1 + 스페이서 1
      mandLayer(p.mand, Y.M10, Y.M11, f(ST.m1), f(ST.pull1), "m1", true);
      spacerStage({ pieces:p.mand, walls:p.sp1, y0:Y.M10, y1:Y.M11, t:p.t1, fDep:clamp(f(ST.sp1) * 2), fEb:clamp(f(ST.sp1) * 2 - 1),
        fPull:f(ST.pull1), thinMax:p.thin, consume:f(ST.xm2), c:"sp1", final:false });
      // 맨드릴 2 층: 스페이서 1 모양으로 전사 → 기둥 → 제거
      const m2p = p.m2.flatMap(ringFp);
      mandLayer(m2p, Y.M20, Y.M21, f(ST.xm2), f(ST.pull2), "m2", false);
      spacerStage({ pieces:m2p, walls:p.sp2, y0:Y.M20, y1:Y.M21, t:p.t2, fDep:clamp(f(ST.sp2) * 2), fEb:clamp(f(ST.sp2) * 2 - 1),
        fPull:f(ST.pull2), thinMax:p.thin, consume:fT * (state.eb === 2 ? 1 : .5), c:"sp2", final:true });
    }
  }
  return B;
}

// ---------- Three.js ----------
let renderer, scene, camera, controls, GEO, EDGE;
const pool = [];
function draw(B) {
  let used = 0;
  for (const b of B) {
    let { x0, x1, y0, y1, z0, z1 } = b;
    if (state.sec) z1 = Math.min(z1, 0);
    if (x1 - x0 < .01 || y1 - y0 < .01 || z1 - z0 < .01) continue;
    let m = pool[used];
    if (!m) {
      m = new THREE.Mesh(GEO, new THREE.MeshStandardMaterial({ roughness:.55, metalness:.05, polygonOffset:true, polygonOffsetFactor:1, polygonOffsetUnits:1 }));
      const e = new THREE.LineSegments(EDGE, new THREE.LineBasicMaterial({ color:0x1f2937, transparent:true, opacity:.22 }));
      m.add(e); m.userData.e = e; scene.add(m); pool.push(m);
    }
    used++;
    m.visible = true;
    m.scale.set(x1 - x0, y1 - y0, z1 - z0); m.position.set((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
    const mat = m.material, op = b.op ?? 1, tr = op < 1;
    mat.color.setHex(COL[b.c]);
    if (mat.transparent !== tr) { mat.transparent = tr; mat.needsUpdate = true; }
    mat.opacity = op; mat.depthWrite = !tr;
    m.userData.e.visible = !b.noEdge;
  }
  for (let i = used; i < pool.length; i++) pool[i].visible = false;
}
function init() {
  const canvas = document.getElementById("c");
  renderer = new THREE.WebGLRenderer({ canvas, antialias:true, alpha:true, preserveDrawingBuffer:true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(30, 1, 1, 3000);
  scene.add(new THREE.HemisphereLight(0xffffff, 0xb8c2d0, .85));
  const d1 = new THREE.DirectionalLight(0xffffff, .75); d1.position.set(80, 160, 120); scene.add(d1);
  const d2 = new THREE.DirectionalLight(0xffffff, .3); d2.position.set(-100, 60, -80); scene.add(d2);
  GEO = new THREE.BoxGeometry(1, 1, 1); EDGE = new THREE.EdgesGeometry(GEO);
  controls = new THREE.OrbitControls(camera, canvas);
  controls.enableDamping = true;
  resetView();
  new ResizeObserver(resize).observe(canvas.parentElement); resize();
}
function resetView() {
  if (!controls) return;
  if (state.top) { camera.position.set(0, 480, 1); controls.target.set(0, 0, 0); }
  else if (state.sec) { camera.position.set(30, 110, 340); controls.target.set(0, 8, -40); }
  else { camera.position.set(250, 210, 330); controls.target.set(0, 10, 0); }
  controls.update();
}
function resize() {
  const el = renderer.domElement.parentElement, w = el.clientWidth, h = el.clientHeight;
  renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
}
let last = performance.now();
function tick(now) {
  const dt = Math.min(.05, (now - last) / 1000); last = now;
  anim.s += (state.step - anim.s) * (1 - Math.pow(.02, dt));
  if (Math.abs(state.step - anim.s) < .001) anim.s = state.step;
  draw(build()); controls.update(); renderer.render(scene, camera);
  requestAnimationFrame(tick);
}

// ---------- 측정 · 판정 ----------
const r1 = v => Math.round(v * 10) / 10;
function measure() {
  const p = params(1, 1), { ls, sp } = spaces(p);
  const widths = ls.map(l => l.x1 - l.x0), cent = ls.map(l => (l.x0 + l.x1) / 2);
  const pitches = cent.slice(1).map((c, i) => c - cent[i]);
  const byCls = {};
  sp.forEach(s => (byCls[s.cls] ||= []).push(s.w));
  return { p, widths, pitches, byCls, walk:Math.max(...pitches) - Math.min(...pitches),
    minSpace:Math.min(...sp.map(s => s.w)), ideal:MODE === "sadp" ? 40 : 20 };
}
function renderMeasure() {
  const m = measure(), el = document.getElementById("meas");
  const rows = Object.keys(SPACE).map(k => {
    const v = m.byCls[k] || [], [name, col, what] = SPACE[k];
    const val = v.length ? r1(v[0]) : "—";
    return `<tr><td><i style="background:#${COL[col].toString(16).padStart(6, "0")}"></i>${name} 공간</td><td>${what}</td><td class="n">${val <= 0 ? "붙음" : val}</td></tr>`;
  }).join("");
  const pt = [...new Set(m.pitches.map(r1))].join(" / ");
  el.innerHTML = `<table><tbody>
    <tr><td>최종 선폭</td><td>${MODE === "sadp" ? "스페이서 두께" : "스페이서 2 두께"}</td><td class="n">${r1(m.widths[1] ?? m.widths[0])}</td></tr>
    ${rows}
    <tr><td>피치</td><td>선 중심 간격 (목표 ${m.ideal})</td><td class="n">${pt}</td></tr>
    <tr><td><b>피치 워킹</b></td><td>최대 − 최소 피치</td><td class="n"><b>${r1(m.walk)}</b></td></tr></tbody></table>`;
  return m;
}
function verdict() {
  const m = renderMeasure(), v = document.getElementById("verdict"), msgs = [];
  let lv = 0; // 0 ok, 1 mid, 2 bad
  const up = l => { lv = Math.max(lv, l); };
  if (m.minSpace <= .3) { up(2); msgs.push(`<strong>선이 붙음</strong>공간 하나가 0이 되어 이웃한 두 선이 한 덩어리가 됐다 (short). 맨드릴 CD와 스페이서 두께의 합이 초기 피치 예산을 넘었다.`); }
  else if (m.walk > 4) { up(2); msgs.push(`<strong>피치 워킹 큼 (${r1(m.walk)})</strong>공간 집단끼리 크기가 달라 피치가 번갈아 바뀐다. 평균 피치는 그대로 ${m.ideal}이라 평균만 재면 안 보인다. 선마다 저항·용량이 달라지고, 좁은 쪽 공간은 다음 식각에서 덜 열릴 수 있다.`); }
  else if (m.walk > 1) { up(1); msgs.push(`<strong>피치 워킹 있음 (${r1(m.walk)})</strong>공간 집단 사이에 차이가 생겼다. 색으로 칠한 공간의 폭을 비교해 보세요.`); }
  else msgs.push(`<strong>피치 균일</strong>모든 공간이 같아 피치가 ${m.ideal}으로 고르다. ${MODE === "sadp" ? "코어 = 갭 조건 (C = P₀/2 − t)" : "α = β = γ 조건"}을 만족한다.`);
  if (state.eb === 1) { up(2); msgs.push(`<strong>에치백 부족 → 브리지</strong>스페이서 사이 바닥에 막이 남았다 (진보라). 맨드릴이 있던 자리만 열리고 나머지 공간은 막혀, 전사 후 대상막이 한 덩어리로 이어진다 (빨강).`); }
  if (state.eb === 2) { up(1); msgs.push(`<strong>에치백 과다 → 마스크 높이 부족</strong>스페이서 윗부분이 깎여 키가 낮아졌다. 전사 도중 마스크가 먼저 바닥나 대상막 선의 윗부분이 깎인다 (선 높이 손실). 두께가 남아 있어도 깎인 모서리(faceting)가 CD를 바꾼다.`); }
  if (state.pull) { up(1); msgs.push(`<strong>맨드릴 제거 선택비 부족</strong>맨드릴을 빼는 동안 스페이서도 양옆이 깎여 선폭이 ${r1(m.widths[1] ?? m.widths[0])}로 줄었다${MODE === "saqp" ? " (두 번의 제거에서 모두 깎임 — 맨드릴 2도 가늘어짐)" : ""}. 피치는 그대로지만 선은 가늘고 공간은 넓어진다.`); }
  v.className = "verdict " + ["v-ok", "v-mid", "v-bad"][lv];
  v.innerHTML = msgs.join("<br><br>");
}

// ---------- UI ----------
const $ = id => document.getElementById(id);
const STEPS = window.SP_STEPS;
function go(i) {
  state.step = Math.max(0, Math.min(NSTEP - 1, i));
  const s = STEPS[state.step];
  [...$("steps").children].forEach((b, j) => j === state.step ? b.setAttribute("aria-current", "step") : b.removeAttribute("aria-current"));
  $("kind").textContent = s.kind; $("kind").className = "kind" + (s.etch ? " etch" : "");
  $("title").textContent = s.title; $("desc").textContent = s.desc;
  $("facts").innerHTML = s.facts.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join("");
  $("prev").disabled = state.step === 0; $("next").disabled = state.step === NSTEP - 1;
  verdict();
}
STEPS.forEach((s, i) => {
  const b = document.createElement("button"); b.textContent = i;
  b.title = s.title; b.setAttribute("aria-label", s.title); if (s.etch) b.classList.add("etch");
  b.onclick = () => go(i); $("steps").appendChild(b);
});
$("prev").onclick = () => go(state.step - 1);
$("next").onclick = () => go(state.step + 1);
document.addEventListener("keydown", e => { if (e.target.tagName === "INPUT") return; if (e.key === "ArrowRight") go(state.step + 1); if (e.key === "ArrowLeft") go(state.step - 1); });

const toXfer = () => { if (state.step < ST.xfer) go(ST.xfer); else verdict(); };
function slider(id, key) {
  $(id).oninput = e => { state[key] = +e.target.value; $(id + "Val").textContent = (state[key] > 0 ? "+" : "") + state[key]; toXfer(); };
}
slider("dc", "dc"); slider("dt", "dt");
function seg(id, key) {
  $(id).querySelectorAll("button").forEach(b => b.onclick = () => {
    state[key] = +b.dataset.v;
    $(id).querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x === b));
    toXfer();
  });
}
seg("eb", "eb"); seg("pull", "pull");
$("bReset2").onclick = () => {
  Object.assign(state, { dc:0, dt:0, eb:0, pull:0 }); syncInputs(); verdict();
};
function syncInputs() {
  for (const k of ["dc", "dt"]) { $(k).value = state[k]; $(k + "Val").textContent = (state[k] > 0 ? "+" : "") + state[k]; }
  for (const k of ["eb", "pull"]) $(k).querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", +b.dataset.v === state[k]));
  $("bSec").setAttribute("aria-pressed", state.sec); $("bTop").setAttribute("aria-pressed", state.top);
}
$("bSec").onclick = () => { state.sec = !state.sec; if (state.sec) state.top = false; syncInputs(); resetView(); };
$("bTop").onclick = () => { state.top = !state.top; if (state.top) state.sec = false; syncInputs(); resetView(); };
$("bReset").onclick = resetView;

// 주소로 상태 지정 (예: #step=5&dc=4&dt=-2&eb=1&pull=1&sec=1&top=1&instant=1)
function fromHash() {
  const q = new URLSearchParams(location.hash.slice(1));
  for (const k of ["dc", "dt", "eb", "pull"]) if (q.has(k)) state[k] = +q.get(k);
  state.sec = q.get("sec") === "1"; state.top = q.get("top") === "1";
  syncInputs();
  go(q.has("step") ? +q.get("step") : 0);
  resetView();
  if (q.get("instant") === "1") anim.s = state.step;
}
try {
  if (!window.THREE || !THREE.OrbitControls) throw new Error("lib");
  init(); fromHash(); requestAnimationFrame(tick);
} catch (e) { $("fallback").style.display = "grid"; fromHash(); }
window.addEventListener("hashchange", fromHash);
})();
