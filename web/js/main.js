const socket = io();

let myCharacter = null;
let myLatestHand = [];
let mySeat = null;

function canUseAsBang(card) {
  return card.type === "BANG" ||
    (myCharacter === "CALAMITY_JANET" && card.type === "MISSED");
}

window.playBangAt = function playBangAt(targetSeat) {
  const bang = (myLatestHand || []).find(canUseAsBang);

  if (!bang) {
    alert("손패에 뱅!으로 사용할 카드가 없습니다.");
    return;
  }

  socket.emit("action:play", {
    cardId: bang.id,
    targetSeat
  });
};

window.playBeer = function(){
  const beer = (myLatestHand || []).find(c => c.type === 'BEER');
  if (!beer) return alert('손패에 맥주가 없습니다.');
  socket.emit('action:play', { cardId: beer.id });
};

const $ = (id)=>document.getElementById(id);

const logDiv = $("log");
const chatDiv = $("log");
const soundToggle = $("soundToggle");

// Restore last nick/room
const lastRoom = localStorage.getItem("bang:room");
if (lastRoom) $("roomCode").value = lastRoom;

$("btnCreate").onclick = ()=>{
  $("btnCreate").disabled = true;
  const nick = saveNick();
  socket.emit("room:create", { nick });
};
$("btnJoin").onclick = ()=>{
  const code = $("roomCode").value.trim().toUpperCase();
  const nick = saveNick();
  if(!code) return alert("코드를 입력하세요.");
  socket.emit("room:join", { code, nick });
};
$("btnStart").onclick = ()=> socket.emit("game:start");
$("btnEndTurn").onclick = ()=> socket.emit("turn:end");

// Chat actions
$("btnSend").onclick = sendChat;
$("chatInput").addEventListener("keydown", (e)=>{
  if(e.key === "Enter"){
    e.preventDefault();
    sendChat();
  }
});

function sendChat(){
  const text = $("chatInput").value.trim();
  if(!text) return;
  socket.emit("chat:send", { text });
  $("chatInput").value = "";
}

// Copy room code
$("btnCopy").onclick = async ()=>{
  const code = $("currentRoom").innerText.trim();
  if(!code || code === "-") return;
  try {
    await navigator.clipboard.writeText(code);
    toast("방 코드가 복사되었습니다.");
  } catch {
    toast("복사 실패. 수동으로 복사하세요.");
  }
};

    // Leave room (hard disconnect)
$("btnLeave").onclick = ()=>{
  socket.disconnect();
  toast("연결을 종료했습니다. 페이지를 새로고치면 재연결됩니다.");
};

// Save log
$("btnSaveLog").onclick = ()=>{
  const text = Array.from(logDiv.children).map(n => n.textContent).join("\n");
  const blob = new Blob([text], {type:"text/plain;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `bang-log-${new Date().toISOString().replace(/[:.]/g,'-')}.txt`;
  a.click();
  URL.revokeObjectURL(a.href);
};

// Socket events
socket.on("connect", ()=>{
  toast("서버에 연결되었습니다.");
});
socket.on("disconnect", (r)=>{
  toast("연결이 끊어졌습니다.");
});

socket.on("room:created", ({code, seat})=>{
  mySeat = seat;
  $("currentRoom").innerText = code;
  $("roomCode").value = code;
  localStorage.setItem("bang:room", code);
  addLog(`방이 생성되었습니다: ${code}`);
  notify();
});
socket.on("room:joined", ({code, seat, spectator})=>{
  mySeat = seat;
  $("currentRoom").innerText = code;
  localStorage.setItem("bang:room", code);

  if (spectator) {
    addLog(`방에 관전자로 참가했습니다: ${code}`);
  } else {
    addLog(`방에 참가했습니다: ${code}`);
  }

  notify();
});
socket.on("room:update", (state)=>{ lastState = state || lastState;
  const STATUS_KR = {
    LOBBY: "대기 중",
    IN_GAME: "게임 중",
    ENDED: "게임 종료"
  };
  $("status").innerText = STATUS_KR[state.status] || state.status;
  $("turnSeat").innerText = (state.turnSeat ?? "-");
  $("turnSeatView").innerText = (state.turnSeat ?? "-");
  renderPlayers(state.players, state.turnSeat);
  renderPiles(state);
  $("playerCount").textContent = `(${state.players.length}명)`;
});
socket.on("log", ({text})=> { addLog(text); notify(); });
socket.on("chat:append", ({nick, text})=>{
  const line = document.createElement("div");
  line.textContent = `[채팅] ${nick}: ${text}`;
  chatDiv.appendChild(line);
  chatDiv.scrollTop = chatDiv.scrollHeight;
  notify();
});
    
const ROLE_KR = {
  SHERIFF: "보안관",
  DEPUTY: "부관",
  OUTLAW: "무법자",
  RENEGADE: "배신자"
};

socket.on("secret:role", ({role})=>{
  if(role){
    $("roleBadge").style.display="inline-flex";
    $("myRole").textContent = ROLE_KR[role] || role;
  }
});

socket.on('secret:character', ({character}) => {
  console.log('[CHAR]', character);
  myCharacter = character;
  window.myCharacter = character;
});

socket.on("hand:update", ({hand})=>{ renderHand(hand); });

socket.on("prompt:respond", ({needs})=>{ openRespondModal(needs); });

socket.on("error", ({message})=>{
  $("btnCreate").disabled = false;
  alert(message);
});

    
// --------- Game state cache & hand UI ---------
let lastState = { players: [], turnSeat: null };
function renderHand(hand){
  myLatestHand = hand || [];
  const root = $("handArea");
  if(!root) return;
  root.innerHTML = "";
  if(!hand || !hand.length){
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "손패가 없습니다.";
    root.appendChild(empty);
    return;
  }
  hand.forEach((card)=>{
    const btn = document.createElement("button");
    btn.className = "pill";
    btn.style.userSelect = "none";
    btn.dataset.cardId = card.id || "";
    btn.dataset.cardType = card.type || "";
    btn.title = card.type || card.name || "CARD";
    btn.textContent = card.name || card.type || "CARD";
    btn.onclick = ()=>onPlayCard(card);
    root.appendChild(btn);
  });
}

function onPlayCard(card){
  const type = (card.type || "").toUpperCase();

  if (type === "BANG"){
    const candidates = (lastState.players || []).filter(p => p.seat !== mySeat && p.alive);
    if(!candidates.length){
      return alert("유효한 대상이 없습니다.");
    }
    openTargetPicker("Bang! 대상 선택", candidates, (seat)=>{
      socket.emit("action:play", { cardId: card.id, targetSeat: seat });
    });
    return;
  }
  else if (type === "PANIC"){ // 강탈: 거리1 (서버가 거리검증)
    const candidates = (lastState.players || []).filter(p => p.seat !== mySeat && p.alive);
    if(!candidates.length) return alert("유효한 대상이 없습니다.");
    openTargetPicker("강탈 대상 선택", candidates, (seat)=>{
      socket.emit("action:play", { cardId: card.id, targetSeat: seat });
    });
    return;
  }
  else if (type === "DUEL"){ // 결투: 대상 선택
    const candidates = (lastState.players || []).filter(p => p.seat !== mySeat && p.alive);
    if(!candidates.length) return alert("유효한 대상이 없습니다.");
    openTargetPicker("결투 대상 선택", candidates, (seat)=>{
      socket.emit("action:play", { cardId: card.id, targetSeat: seat });
    });
    return;
  }
  else if (type === "INDIANS"){ // 인디언: 대상 없음
    socket.emit("action:play", { cardId: card.id });
    return;
  }
  else if (type === "GATLING"){ // 기관총: 대상 없음
    socket.emit("action:play", { cardId: card.id });
    return;
  }
  else if (type === "CATBALOU"){ // 캣 벌로우: 무제한 거리
    const candidates = (lastState.players || []).filter(p => p.seat !== mySeat && p.alive);
    if(!candidates.length) return alert("유효한 대상이 없습니다.");
    openTargetPicker("캣 벌로우 대상 선택", candidates, (seat)=>{
      socket.emit("action:play", { cardId: card.id, targetSeat: seat });
    });
    return;
  }
  else if (type === "JAIL"){
    const candidates = (lastState.players || []).filter(p => p.seat !== mySeat && p.alive);
    if(!candidates.length) return alert("유효한 대상이 없습니다.");
    openTargetPicker("감옥 대상 선택", candidates, (seat)=>{
      socket.emit("action:play", { cardId: card.id, targetSeat: seat });
    });
    return;
  }

  // 기본: 대상 불필요 카드(맥주 등)
  socket.emit("action:play", { cardId: card.id });
}    

function openTargetPicker(title, candidates, onPick){
  const body = $("modalBody");
  $("modalTitle").textContent = title;
  body.innerHTML = "";
  candidates.forEach(p=>{
    const b = document.createElement("button");
    b.textContent = `${p.nick} (좌석 ${p.seat})`;
    b.style.margin = "4px";
    b.onclick = ()=>{ closeModal(); onPick(p.seat); };
    body.appendChild(b);
  });
  openModal();
}

// Respond modal for Missed! 등
function openRespondModal(needs){
  const body = $("modalBody");
  $("modalTitle").textContent = needs === "MISSED" ? "피격 응수 (Missed!)"
                          : needs === "BANG"   ? "응수 (BANG!)"
                          : "응답 필요";
  body.innerHTML = "";

  if (needs === "MISSED"){
    const has = myLatestHand.find(c =>
      (c.type || "").toUpperCase() === "MISSED" ||
      (myCharacter === "CALAMITY_JANET" && (c.type || "").toUpperCase() === "BANG")
    );
    if(has){
      const use = document.createElement("button");
      use.className = "primary";
      use.textContent = "Missed! 내기";
      use.onclick = ()=>{ closeModal(); socket.emit("action:respond", { cardId: has.id }); };
      body.appendChild(use);
    } else {
      const info = document.createElement("div");
      info.className = "muted"; info.textContent = "Missed! 카드가 없습니다.";
      body.appendChild(info);
    }
  } else if (needs === "BANG"){
    const has = myLatestHand.find(c =>
      (c.type || "").toUpperCase() === "BANG" ||
      (myCharacter === "CALAMITY_JANET" && (c.type || "").toUpperCase() === "MISSED")
    );
    if(has){
      const use = document.createElement("button");
      use.className = "primary";
      use.textContent = "BANG! 내기";
      use.onclick = ()=>{ closeModal(); socket.emit("action:respond", { cardId: has.id }); };
      body.appendChild(use);
    } else {
      const info = document.createElement("div");
      info.className = "muted"; info.textContent = "BANG! 카드가 없습니다.";
      body.appendChild(info);
    }
  }

  const take = document.createElement("button");
  take.className = "danger";
  take.style.marginLeft = "8px";
  take.textContent = "피해 받기";
  take.onclick = ()=>{ closeModal(); socket.emit("action:respond", {}); };
  body.appendChild(take);
  openModal();
}

// ---------------- UI helpers ----------------
function renderPlayers(players, turnSeat){
  const root = $("players");
  root.innerHTML = "";

  const layoutMap = {
    4: [
      { left: "50%", top: "8%" },
      { left: "14%", top: "48%" },
      { left: "50%", top: "88%" },
      { left: "86%", top: "48%" },
    ],
    5: [
      { left: "50%", top: "8%" },
      { left: "16%", top: "38%" },
      { left: "26%", top: "82%" },
      { left: "74%", top: "82%" },
      { left: "84%", top: "38%" },
    ],
    6: [
      { left: "50%", top: "7%" },
      { left: "18%", top: "28%" },
      { left: "16%", top: "68%" },
      { left: "50%", top: "90%" },
      { left: "84%", top: "68%" },
      { left: "82%", top: "28%" },
    ],
    7: [
      { left: "50%", top: "7%" },
      { left: "22%", top: "20%" },
      { left: "12%", top: "55%" },
      { left: "28%", top: "86%" },
      { left: "72%", top: "86%" },
      { left: "88%", top: "55%" },
      { left: "78%", top: "20%" },
    ],
  };

  const positions = layoutMap[players.length] || [];

  players.forEach((p, index)=>{
    const el = document.createElement("div");
    el.className = "card player-card";

    const pos = positions[index] || { left: "50%", top: "50%" };
    el.style.left = pos.left;
    el.style.top = pos.top;

    const board = p.board || {};
    const equips = [];

    if (board.weapon && board.weapon !== "Colt45") equips.push(`무기: ${board.weapon}`);
    if (board.barrel) equips.push("술통");
    if (board.mustang) equips.push("야생마");
    if (board.scope) equips.push("조준경");
    if (board.jail) equips.push("감옥");
    if (board.dynamite) equips.push("다이너마이트");

    const equipText = equips.length ? equips.join(" / ") : "장착 없음";

    const roleText =
      p.revealedRole
        ? `<br/>역할: ${ROLE_KR[p.revealedRole] || p.revealedRole}`
        : "";

    el.innerHTML = `
      <b>${escapeHtml(p.nick)}</b><br/>
      좌석 ${p.seat}<br/>
      HP ${p.hp}/${p.maxHp ?? "?"}<br/>
      손패 ${p.handCount ?? "?"}장
      ${roleText}
      <br/>
      <span class="muted">${escapeHtml(equipText)}</span>
    `;

    if (p.seat === mySeat) {
      el.classList.add("me");
    }

    if (turnSeat !== null && turnSeat === p.seat) {
      el.classList.add("turn");
    }

    root.appendChild(el);
  });

  $("mySeat").innerText = (mySeat ?? "-");
}

function renderPiles(state){
  const root = $("pileArea");
  if(!root) return;

  const top = state.topDiscard;

  root.innerHTML = `
    <div class="card">
      <b>🃏 카드 더미</b><br/>
      남은 카드: ${state.deckCount ?? 0}장
    </div>

    <div class="card">
      <b>🗑️ 버린 더미</b><br/>
      ${
        top
          ? `${escapeHtml(top.name || top.type)}<br/><span class="muted">${escapeHtml(top.rank || "")} ${escapeHtml(top.suit || "")}</span>`
          : `<span class="muted">비어 있음</span>`
      }
    </div>
  `;
}

function addLog(text){
  const line = document.createElement("div");
  line.textContent = text;
  logDiv.appendChild(line);
  logDiv.scrollTop = logDiv.scrollHeight;
}

function saveNick(){
  return $("nick").value || "Player";
}

function toast(msg){
  const t = document.createElement("div");
  t.textContent = msg;
  Object.assign(t.style, {
    position:"fixed", right:"16px", bottom:"16px",
    background:"#222", color:"#fff", padding:"10px 14px",
    borderRadius:"10px", fontSize:"13px", opacity:"0.95", zIndex:9999
  });
  document.body.appendChild(t);
  setTimeout(()=>{ t.remove(); }, 1800);
}

function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

// Notification sound (simple WebAudio beep)
let audioCtx;

function openModal(){
  $("modal").style.display = "flex";
}

function closeModal(){
  $("modal").style.display = "none";
}

$("modalCancel").onclick = closeModal;

function notify(){
  if(!soundToggle.checked) return;
  try{
    if(!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.type = "sine";
    o.frequency.value = 880;
    g.gain.value = 0.02;
    o.connect(g); g.connect(audioCtx.destination);
    o.start();
    setTimeout(()=>{ o.stop(); }, 120);
  }catch(e){ /* ignore */ }
}