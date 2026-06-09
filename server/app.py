from flask import Flask, send_from_directory, request
from flask_socketio import SocketIO, join_room, emit
import random
import string
import os

# =========================
# Flask / Socket.IO 설정
# =========================
app = Flask(__name__, static_folder="../web", static_url_path="")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

# =========================
# 인메모리 상태
# =========================
rooms = {}        # code -> room dict
player_room = {}  # sid -> code

def gen_code(n=5):
    return "".join(random.choice(string.ascii_uppercase) for _ in range(n))

@app.route("/")
def index():
    return send_from_directory("../web", "index.html")

# =========================
# 카드/역할/유틸
# =========================
def build_deck_basic():
    """
    실제 카드 무늬/숫자를 포함한 기본 덱
    suit: heart / diamond / club / spade
    rank: A, 2~10, J, Q, K
    """
    deck = []

    def add_card(name, ctype, color, suit, rank, meta=None):
        card = {
            "id": f"{ctype}-{suit}-{rank}-{random.randint(1000,9999)}",
            "name": name,
            "type": ctype,
            "color": color,
            "suit": suit,
            "rank": str(rank)
        }
        if meta:
            card.update(meta)
        deck.append(card)

    # 갈색 카드
    add_card("뱅!", "BANG", "brown", "heart", "Q")
    add_card("뱅!", "BANG", "brown", "heart", "K")
    add_card("뱅!", "BANG", "brown", "heart", "A")

    for rank in ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]:
        add_card("뱅!", "BANG", "brown", "diamond", rank)

    for rank in ["2","3","4","5","6","7","8","9"]:
        add_card("뱅!", "BANG", "brown", "club", rank)

    add_card("뱅!", "BANG", "brown", "spade", "A")

    for rank in ["2","3","4","5","6","7","8"]:
        add_card("빗나감!", "MISSED", "brown", "spade", rank)

    for rank in ["10","J","Q","K","A"]:
        add_card("빗나감!", "MISSED", "brown", "club", rank)

    for rank in ["6","7","8","9","10","J"]:
        add_card("맥주", "BEER", "brown", "heart", rank)

    add_card("캣 벌로우", "CATBALOU", "brown", "diamond", "9")
    add_card("캣 벌로우", "CATBALOU", "brown", "diamond", "10")
    add_card("캣 벌로우", "CATBALOU", "brown", "diamond", "J")
    add_card("캣 벌로우", "CATBALOU", "brown", "heart", "K")

    add_card("결투", "DUEL", "brown", "diamond", "Q")
    add_card("결투", "DUEL", "brown", "club", "8")
    add_card("결투", "DUEL", "brown", "spade", "J")

    add_card("기관총", "GATLING", "brown", "heart", "10")

    add_card("인디언!", "INDIANS", "brown", "diamond", "K")
    add_card("인디언!", "INDIANS", "brown", "diamond", "A")

    add_card("강탈!", "PANIC", "brown", "diamond", "8")
    add_card("강탈!", "PANIC", "brown", "heart", "J")
    add_card("강탈!", "PANIC", "brown", "heart", "Q")
    add_card("강탈!", "PANIC", "brown", "heart", "A")

    add_card("주점", "SALOON", "brown", "heart", "5")
    add_card("역마차", "STAGECOACH", "brown", "spade", "9")
    add_card("역마차", "STAGECOACH", "brown", "spade", "9")
    add_card("웰스 파고 은행", "WELLS_FARGO", "brown", "heart", "3")

    add_card("잡화점", "GENERAL_STORE", "brown", "club", "9")
    add_card("잡화점", "GENERAL_STORE", "brown", "spade", "Q")

    # 파란색 카드
    add_card("술통", "BARREL", "blue", "spade", "Q")
    add_card("술통", "BARREL", "blue", "spade", "K")

    add_card("다이너마이트", "DYNAMITE", "blue", "heart", "2")

    add_card("감옥", "JAIL", "blue", "heart", "4")
    add_card("감옥", "JAIL", "blue", "spade", "10")
    add_card("감옥", "JAIL", "blue", "spade", "J")

    add_card("야생마", "MUSTANG", "blue", "heart", "8")
    add_card("야생마", "MUSTANG", "blue", "heart", "9")

    add_card("조준경", "SCOPE", "blue", "spade", "A")

    add_card("레밍턴", "WEAPON", "blue", "club", "K", {"weapon": "REMINGTON"})
    add_card("카빈", "WEAPON", "blue", "club", "A", {"weapon": "CARBINE"})

    add_card("스코필드", "WEAPON", "blue", "club", "J", {"weapon": "SCHOFIELD"})
    add_card("스코필드", "WEAPON", "blue", "club", "Q", {"weapon": "SCHOFIELD"})
    add_card("스코필드", "WEAPON", "blue", "spade", "K", {"weapon": "SCHOFIELD"})

    add_card("볼캐닉", "WEAPON", "blue", "club", "10", {"weapon": "VOLCANIC"})
    add_card("볼캐닉", "WEAPON", "blue", "spade", "10", {"weapon": "VOLCANIC"})

    add_card("윈체스터", "WEAPON", "blue", "spade", "8", {"weapon": "WINCHESTER"})

    random.shuffle(deck)
    return deck

ROLE_POOL = {
    4: ["SHERIFF", "OUTLAW", "OUTLAW", "RENEGADE"],
    5: ["SHERIFF", "DEPUTY", "OUTLAW", "OUTLAW", "RENEGADE"],
    6: ["SHERIFF", "DEPUTY", "OUTLAW", "OUTLAW", "OUTLAW", "RENEGADE"],
    7: ["SHERIFF", "DEPUTY", "DEPUTY", "OUTLAW", "OUTLAW", "OUTLAW", "RENEGADE"],
}

CHARACTER_POOL = [
    {"name":"WILLY_THE_KID",     "hp":4},
    {"name":"CALAMITY_JANET",    "hp":4},
    {"name":"KIT_CARLSON",       "hp":4},
    {"name":"BART_CASSIDY",      "hp":4},
    {"name":"SID_KETCHUM",       "hp":4},
    {"name":"LUCKY_DUKE",        "hp":4},
    {"name":"JOURDONNAIS",       "hp":4},
    {"name":"BLACK_JACK",        "hp":4},
    {"name":"VULTURE_SAM",       "hp":4},
    {"name":"JESSE_JONES",       "hp":4},
    {"name":"SUZY_LAFAYETTE",    "hp":4},
    {"name":"PEDRO_RAMIREZ",     "hp":4},
    {"name":"SLAB_THE_KILLER",   "hp":4},
    {"name":"ROSE_DOOLAN",       "hp":4},
    {"name":"PAUL_REGRET",       "hp":3},
    {"name":"EL_GRINGO",         "hp":3},
]

def public_state(code):
    r = rooms.get(code, {})
    players_pub = []
    for p in r.get("players", []):
        players_pub.append({
            "nick": p["nick"],
            "seat": p["seat"],
            "hp": p["hp"],
            "maxHp": p.get("max_hp"),
            "alive": p["alive"],
            "revealedRole": p.get("revealedRole"),
            "character": p.get("character"),
            "board": p.get("board", {}),
            "handCount": len(p.get("hand", [])),
            "deckCount": len(r["deck"]),
            "topDiscard": r["discard"][-1] if r["discard"] else None
        })
    turn_seat = None
    if r.get("players") and r.get("status") == "IN_GAME":
        turn_seat = r["players"][r["turn_idx"]]["seat"]
    return {
        "code": code,
        "status": r.get("status", "LOBBY"),
        "players": players_pub,
        "spectators": [
            {"nick": s["nick"]}
            for s in r.get("spectators", [])
        ],
        "turnSeat": turn_seat,
        "pending": (r.get("pending") or {}).get("kind")  # 예: 'ATTACK'
    }

def broadcast_state(code):
    socketio.emit("room:update", public_state(code), room=code)

def dm_hand(p):
    socketio.emit("hand:update", {"hand": p["hand"]}, to=p["sid"])

def dm_role(p):
    socketio.emit("secret:role", {"role": p["role"]}, to=p["sid"])

def dm_character(p):
    socketio.emit("secret:character", {"character": p["character"]}, to=p["sid"])

def get_room_by_sid(sid):
    code = player_room.get(sid)
    if not code:
        return None, None
    return code, rooms.get(code)

def get_player_by_sid(r, sid):
    for p in r["players"]:
        if p["sid"] == sid:
            return p
    return None

def alive_players(r):
    return [p for p in r["players"] if p["alive"]]

def draw_one(r):
    if not r["deck"]:

        if len(r["discard"]) <= 1:
            return None

        top_discard = r["discard"].pop()

        r["deck"] = r["discard"]
        r["discard"] = [top_discard]

        random.shuffle(r["deck"])

        announce(
            r["code"],
            f"카드 더미가 소진되어 버린 카드 {len(r['deck'])}장을 섞어 새 카드 더미를 만들었습니다."
        )

    return r["deck"].pop() if r["deck"] else None

def reveal_one(r):
    """
    카드 펼치기:
    덱 맨 위 카드 1장을 공개하고, 버린 카드 더미로 보낸다.
    """
    card = draw_one(r)
    if card:
        discard_cards(r, [card])
    return card

def reveal_for_player(r, p, prefer_func=None):
    """
    카드 펼치기.
    럭키 듀크면 2장을 펼치고 유리한 카드 1장을 자동 선택한다.
    선택하지 않은 카드도 버린 카드 더미로 간다.
    """
    if p.get("character") == "LUCKY_DUKE":
        cards = []

        first = draw_one(r)
        second = draw_one(r)

        if first:
            cards.append(first)
        if second:
            cards.append(second)

        if not cards:
            return None

        chosen = cards[0]

        if prefer_func:
            preferred = [c for c in cards if prefer_func(c)]
            if preferred:
                chosen = preferred[0]

        discard_cards(r, cards)

        announce(
            r["code"],
            f"{p['nick']} 럭키 듀크 능력 발동! "
            f"펼친 카드: {', '.join([c['rank'] + ' ' + c['suit'] for c in cards])} / "
            f"선택: {chosen['rank']} {chosen['suit']}"
        )

        return chosen

    return reveal_one(r)

def is_heart(card):
    return card and card.get("suit") == "heart"


def is_dynamite_explode(card):
    return (
        card
        and card.get("suit") == "spade"
        and card.get("rank") in ["2", "3", "4", "5", "6", "7", "8", "9"]
    )

def draw_n(r, n):
    cards = []
    for _ in range(n):
        c = draw_one(r)
        if c: cards.append(c)
    return cards

def discard_cards(r, cards):
    r["discard"].extend(cards)

def check_suzy(r, p):
    if (
        p.get("character") == "SUZY_LAFAYETTE"
        and p["alive"]
        and len(p["hand"]) == 0
    ):
        drew = draw_n(r, 1)
        if drew:
            p["hand"].extend(drew)
            dm_hand(p)
            announce(r["code"], f"{p['nick']} 수지 라파예트 능력 발동! 카드 1장 드로우")

def next_turn_index(r):
    if not r["players"]: return 0
    n = len(r["players"])
    i = (r["turn_idx"] + 1) % n
    # 죽은 플레이어는 스킵
    while not r["players"][i]["alive"]:
        i = (i + 1) % n
    return i

# ---------- 거리/무기 유틸 ----------

def alive_ordered_seats(r):
    """생존자 좌석을 원형 순서(좌석 번호 오름차순)로 반환"""
    return [p["seat"] for p in r["players"] if p["alive"]]

def ring_distance_on_alive(r, seatA, seatB):
    """사망자 건너뛴 원형 최단거리"""
    seats = alive_ordered_seats(r)
    if seatA not in seats or seatB not in seats or not seats:
        return 0
    n = len(seats)
    ia = seats.index(seatA)
    ib = seats.index(seatB)
    diff = abs(ia - ib)
    return min(diff, n - diff)

def weapon_range(weapon_name):
    table = {
        "Colt45": 1,
        "VOLCANIC": 1,   # (특수: 무한 뱅)
        "SCHOFIELD": 2,
        "REMINGTON": 3,
        "CARBINE": 4,
        "WINCHESTER": 5
    }
    return table.get(weapon_name or "Colt45", 1)

def has_unlimited_bang(p):
    """볼캐닉 or 윌리 더 키드(캐릭터)면 뱅 무제한"""
    if p["board"].get("weapon") == "VOLCANIC":
        return True
    if p.get("character") == "WILLY_THE_KID":
        return True
    return False

def dist_with_modifiers(r, viewer, target):
    """
    viewer가 target을 '볼 때'의 유효 거리
    - 기본: 원형 최단거리(사망자 제외)
    - +1: target이 MUSTANG 또는 PAUL_REGRET
    - -1: viewer가 SCOPE 또는 ROSE_DOOLAN
    - 최소 1 보정
    """
    d = ring_distance_on_alive(r, viewer["seat"], target["seat"])
    # target 측 +1
    if target["board"].get("mustang"): d += 1
    if target.get("character") == "PAUL_REGRET": d += 1
    # viewer 측 -1
    if viewer["board"].get("scope"): d -= 1
    if viewer.get("character") == "ROSE_DOOLAN": d -= 1
    if d < 1: d = 1
    return d

def assign_roles(r):
    n = len(r["players"])
    pool = ROLE_POOL.get(n)
    if not pool:
        return False, "지원 인원은 4~7명입니다."
    roles = pool[:]
    random.shuffle(roles)
    for i, p in enumerate(r["players"]):
        role = roles[i]
        p["role"] = role
        p["revealedRole"] = "SHERIFF" if role == "SHERIFF" else None
    return True, None

def assign_characters_and_setup(r):
    # 플레이어 수만큼 캐릭터 무작위 샘플링(중복 없음)
    n = len(r["players"])
    if n > len(CHARACTER_POOL):
        return False, "캐릭터 풀이 부족합니다."
    chars = random.sample(CHARACTER_POOL, n)
    for i, p in enumerate(r["players"]):
        ch = chars[i]
        p["character"] = ch["name"]
        base_hp = ch["hp"]
        if p["role"] == "SHERIFF":
            base_hp += 1  # 보안관 +1
        p["max_hp"] = base_hp
        p["hp"] = base_hp
        p["hand"] = []
        p["board"] = {
            "weapon": "Colt45",   # 기본 사정거리 1
            "barrel": False,      # 술통
            "jail": False,        # 감옥에 갇힌 상태(부착됨)
            "dynamite": False,     # 다이너마이트 보유 중
            "mustang": False,    # 다른 사람이 나를 볼 때 +1
            "scope": False       # 내가 남을 볼 때 -1
        }
        p["bang_used"] = False
        p["alive"] = True
    return True, None

def deal_initial_hands(r, n_cards=4):
    for p in r["players"]:
        p["hand"].extend(draw_n(r, n_cards))
        dm_hand(p)

def announce(code, text):
    socketio.emit("log", {"text": text}, room=code)

def check_victory(r, alive_roles_before=None):
    """승리 조건"""
    if r["status"] != "IN_GAME":
        return False

    alive = [p for p in r["players"] if p["alive"]]

    sheriff_alive = any(p["role"] == "SHERIFF" for p in alive)
    outlaw_alive = any(p["role"] == "OUTLAW" for p in alive)
    renegade_alive = any(p["role"] == "RENEGADE" for p in alive)

    # 보안관 사망
    if not sheriff_alive:
        r["status"] = "ENDED"

        was_final_duel = (
            alive_roles_before is not None
            and sorted(alive_roles_before) == sorted(["SHERIFF", "RENEGADE"])
        )

        if len(alive) == 1 and renegade_alive and was_final_duel:
            announce(r["code"], "배신자 승리!")
        else:
            announce(r["code"], "보안관이 사망했습니다. 무법자 승리!")

        return True

    # 보안관 생존 + 무법자와 배신자 모두 제거
    if not outlaw_alive and not renegade_alive:
        r["status"] = "ENDED"
        announce(r["code"], "무법자와 배신자가 모두 제거되었습니다. 보안관 팀 승리!")
        return True

    return False

def handle_death(r, victim, alive_roles_before=None, killer=None):
    victim["alive"] = False
    victim["revealedRole"] = victim["role"]

    announce(r["code"], f"{victim['nick']} 가 제거되었습니다. 역할: {victim['role']}")

    # --- 벌쳐 샘 능력: 죽은 플레이어의 손패 + 장착 카드 획득 ---
    vulture_sam = next(
        (
            p for p in r["players"]
            if p["alive"]
            and p.get("character") == "VULTURE_SAM"
            and p["sid"] != victim["sid"]
        ),
        None
    )

    if vulture_sam:
        gained = []

        # 손패 획득
        gained.extend(victim["hand"])
        victim["hand"] = []

        # 장착 카드 획득: 현재 board는 실제 카드 객체가 아니므로 가상 카드로 생성
        for slot, proto in list_board_slots(victim):
            if slot == "weapon" and proto.get("weapon") == "Colt45":
                continue

            gained.append({
                "id": f"SYN-VULTURE-{proto['type']}-{random.randint(1000,9999)}",
                **proto
            })

            remove_board_slot(victim, slot)

        if gained:
            vulture_sam["hand"].extend(gained)
            dm_hand(vulture_sam)
            announce(
                r["code"],
                f"{vulture_sam['nick']} 벌쳐 샘 능력 발동! "
                f"{victim['nick']}의 카드 {len(gained)}장 획득"
            )

    # --- 무법자 처치 보상 ---
    if killer and killer["alive"] and victim["role"] == "OUTLAW":
        reward = draw_n(r, 3)
        killer["hand"].extend(reward)
        dm_hand(killer)
        announce(r["code"], f"{killer['nick']} 무법자 처치! 카드 3장 획득")

    # --- 보안관이 부관 처치 패널티 ---
    if killer and killer["role"] == "SHERIFF" and victim["role"] == "DEPUTY":
        discard_cards(r, killer["hand"])
        killer["hand"] = []
        dm_hand(killer)

        killer["board"] = {
            "weapon": "Colt45",
            "barrel": False,
            "jail": False,
            "dynamite": False,
            "mustang": False,
            "scope": False
        }

        announce(r["code"], f"{killer['nick']} 부관 오살! 모든 카드 및 장착물 제거")

    # --- 사망자 카드 정리 ---
    discard_cards(r, victim["hand"])
    victim["hand"] = []

    victim["board"] = {
        "weapon": "Colt45",
        "barrel": False,
        "jail": False,
        "dynamite": False,
        "mustang": False,
        "scope": False
    }

    return check_victory(r, alive_roles_before)

# ---------- 턴 시작 훅/판정 유틸 ----------

def set_pending_duel(r, a_seat, b_seat):
    r["pending"] = {"kind":"DUEL", "a":a_seat, "b":b_seat, "turn":"b"}
    target = next(p for p in r["players"] if p["seat"] == b_seat)
    socketio.emit("prompt:respond", {"needs":"BANG"}, to=target["sid"])
    announce(r["code"], f"⚔️ 결투 시작: {r['players'][a_seat]['nick']} vs {r['players'][b_seat]['nick']}")

def step_duel(r, responder_sid, card_id=None):
    pend = r.get("pending") or {}
    if pend.get("kind") != "DUEL": return
    a = next(p for p in r["players"] if p["seat"] == pend["a"])
    b = next(p for p in r["players"] if p["seat"] == pend["b"])
    curr = a if pend["turn"] == "a" else b
    nxt  = b if curr is a else a
    # 응답자 검증
    if curr["sid"] != responder_sid:
        emit("error", {"message":"당신의 응답 차례가 아닙니다."}); return

    # BANG 카드 제출 검사
    defended = False
    if card_id:
        idx, card = ensure_has_card(curr, card_id)
        if card and can_use_as(card, "BANG", curr):
            used = curr["hand"].pop(idx)
            discard_cards(r, [used])
            dm_hand(curr)
            check_suzy(r, curr)
            defended = True

    if defended:
        # 교대
        r["pending"]["turn"] = "a" if pend["turn"] == "b" else "b"
        socketio.emit("prompt:respond", {"needs":"BANG"}, to=nxt["sid"])
        announce(r["code"], f"{curr['nick']} → BANG! (결투 계속)")
    else:
        # BANG 못 냈다 → 피해1 받고 종료
        ended = apply_damage(r, curr, 1, source=nxt)
        r["pending"] = None
        if not ended:
            announce(r["code"], f"⚔️ 결투 종료: {curr['nick']} 피해 1")
        broadcast_state(r["code"])

def set_pending_queue(r, kind, attacker_seat, victims, needs):
    """INDIANS/GATLING: victims는 seat 리스트"""
    r["pending"] = {"kind":kind, "attacker":attacker_seat, "queue":victims, "needs":needs}
    _prompt_next_in_queue(r)

def _prompt_next_in_queue(r):
    pend = r.get("pending") or {}
    if not pend or not pend.get("queue"):
        r["pending"] = None
        broadcast_state(r["code"])
        return

    seat = pend["queue"][0]
    target = next(p for p in r["players"] if p["seat"] == seat)

    # GATLING에서만 술통 자동 판정 먼저
    if pend["kind"] == "GATLING" and target["board"].get("barrel"):
        revealed = reveal_for_player(r, target, prefer_func=is_heart)

        if revealed and is_heart(revealed):
            announce(
                r["code"],
                f"{target['nick']} : 🍺 술통 판정 성공! 기관총 회피 "
                f"({revealed['rank']} {revealed['suit']})"
            )
            pend["queue"].pop(0)
            return _prompt_next_in_queue(r)
        else:
            if revealed:
                announce(
                    r["code"],
                    f"{target['nick']} : 🍺 술통 판정 실패 "
                    f"({revealed['rank']} {revealed['suit']})"
                )
            else:
                announce(
                    r["code"],
                    f"{target['nick']} : 🍺 술통 판정 카드 없음 (실패)"
                )

    socketio.emit("prompt:respond", {"needs": pend["needs"]}, to=target["sid"])

def next_alive_right(r, seat):
    """시계 방향 다음 생존자(턴 진행용)"""
    n = len(r["players"])
    i = (seat + 1) % n
    while not r["players"][i]["alive"]:
        i = (i + 1) % n
    return i

def next_alive_left(r, seat):
    """반시계 방향(왼쪽) 생존자(다이너마이트 전달용)"""
    n = len(r["players"])
    i = (seat - 1) % n
    while not r["players"][i]["alive"]:
        i = (i - 1) % n
    return i

def apply_damage(r, target, amount, source=None):
    alive_roles_before = [p["role"] for p in r["players"] if p["alive"]]

    target["hp"] -= amount
    announce(r["code"], f"{target['nick']} 피해 {amount}! (HP {target['hp']}/{target['max_hp']})")

    if target.get("character") == "BART_CASSIDY" and target["alive"]:
        drew = draw_n(r, amount)
        target["hand"].extend(drew)
        dm_hand(target)
        announce(r["code"], f"{target['nick']} 바트 캐시디 능력 발동! 카드 {len(drew)}장 획득")

    if (
        target.get("character") == "EL_GRINGO"
        and source
        and source["alive"]
        and source.get("hand")
        and target["alive"]
    ):
        stolen_count = 0

        for _ in range(amount):
            if not source["hand"]:
                break

            i = random.randrange(len(source["hand"]))
            stolen = source["hand"].pop(i)
            target["hand"].append(stolen)
            stolen_count += 1

        dm_hand(source)
        dm_hand(target)

        if stolen_count > 0:
            announce(
                r["code"],
                f"{target['nick']} 엘 그링고 능력 발동! {source['nick']}의 손패 {stolen_count}장 획득"
            )

    if target["hp"] <= 0:
        ended = handle_death(r, target, alive_roles_before, killer=source)
        if ended:
            broadcast_state(r["code"])
            return True
        
    return False

def resolve_dynamite(r, curr):
    """턴 시작: 다이너마이트 → 실제 카드 펼치기로 폭발/이동 처리"""
    if not curr["board"].get("dynamite"):
        return False

    revealed = reveal_for_player(
        r,
        curr,
        prefer_func=lambda c: not is_dynamite_explode(c)
    )

    if is_dynamite_explode(revealed):
        curr["board"]["dynamite"] = False
        announce(
            r["code"],
            f"💥 다이너마이트 폭발! {curr['nick']} 피해 3 "
            f"({revealed['rank']} {revealed['suit']})"
        )
        apply_damage(r, curr, 3, source=None)
        return True

    left_idx = next_alive_left(r, curr["seat"])
    curr["board"]["dynamite"] = False
    r["players"][left_idx]["board"]["dynamite"] = True

    if revealed:
        announce(
            r["code"],
            f"🧨 다이너마이트 판정 통과 "
            f"({revealed['rank']} {revealed['suit']}) → "
            f"{r['players'][left_idx]['nick']}에게 넘어갑니다."
        )
    else:
        announce(
            r["code"],
            f"🧨 다이너마이트 판정 카드 없음 → "
            f"{r['players'][left_idx]['nick']}에게 넘어갑니다."
        )

    return True

def resolve_jail(r, curr):
    """턴 시작: 감옥 → 실제 카드 펼치기로 판정"""
    if not curr["board"].get("jail"):
        return False, False  # (resolved, skip_turn)

    revealed = reveal_for_player(r, curr, prefer_func=is_heart)
    curr["board"]["jail"] = False

    if is_heart(revealed):
        announce(
            r["code"],
            f"🔓 감옥 판정 성공! {curr['nick']} 턴 진행 "
            f"({revealed['rank']} {revealed['suit']})"
        )
        return True, False

    if revealed:
        announce(
            r["code"],
            f"🚫 감옥 판정 실패! {curr['nick']} 턴 스킵 "
            f"({revealed['rank']} {revealed['suit']})"
        )
    else:
        announce(
            r["code"],
            f"🚫 감옥 판정 카드 없음! {curr['nick']} 턴 스킵"
        )

    return True, True

def start_turn(r):
    """턴 시작: bang_used 리셋 → 다이너마이트 → 감옥 → (살아 있고 스킵이 아니면) 드로우2"""
    curr = r["players"][r["turn_idx"]]
    if not curr["alive"]:
        r["turn_idx"] = next_turn_index(r)
        return start_turn(r)

    curr["bang_used"] = False

    # 1) 다이너마이트
    if resolve_dynamite(r, curr):
        # 폭발로 사망해 게임이 끝났을 수 있음
        if r["status"] != "IN_GAME":
            return
        # 다이너 처리 후에도 살아 있으면 계속 진행
        pass

    # 2) 감옥
    _, skip = resolve_jail(r, curr)
    if skip:
        # 다음 생존자에게 턴 넘김
        r["turn_idx"] = next_alive_right(r, r["turn_idx"])
        broadcast_state(r["code"])
        return start_turn(r)

    # 3) 드로우 단계
    if curr.get("character") == "JESSE_JONES":
        candidates = [
            p for p in alive_players(r)
            if p["sid"] != curr["sid"] and len(p["hand"]) > 0
        ]

        if candidates:
            target = random.choice(candidates)
            i = random.randrange(len(target["hand"]))
            stolen = target["hand"].pop(i)

            curr["hand"].append(stolen)
            curr["hand"].extend(draw_n(r, 1))

            dm_hand(target)
            dm_hand(curr)

            announce(
                r["code"],
                f"{curr['nick']} 제시 존스 능력 발동! {target['nick']}의 손패 1장을 가져오고 카드 1장을 드로우."
            )
        else:
            drew = draw_n(r, 2)
            curr["hand"].extend(drew)
            dm_hand(curr)
            announce(r["code"], f"{curr['nick']} 님의 차례 (카드 2장 드로우).")

    elif curr.get("character") == "KIT_CARLSON":
        looked = draw_n(r, 3)

        take = looked[:2]
        put_back = looked[2:]

        curr["hand"].extend(take)

        # 남은 1장은 덱 맨 위로 되돌림
        for card in reversed(put_back):
            r["deck"].append(card)

        dm_hand(curr)

        announce(
            r["code"],
            f"{curr['nick']} 키트 칼슨 능력 발동! 카드 3장을 보고 2장을 가져갑니다."
        )

    else:
        drew = []

        # 페드로 라미레즈: 첫 카드 discard에서 가져오기
        if curr.get("character") == "PEDRO_RAMIREZ" and r["discard"]:
            first = r["discard"].pop()
            drew.append(first)

            announce(
                r["code"],
                f"{curr['nick']} 페드로 능력 발동! 버린 카드 더미에서 카드 1장 획득"
            )
        else:
            first = draw_one(r)
            if first:
                drew.append(first)

        # 두 번째 카드는 항상 덱에서
        second = draw_one(r)
        if second:
            drew.append(second)

        curr["hand"].extend(drew)

        # 🔥 블랙 잭 처리 그대로 유지
        if curr.get("character") == "BLACK_JACK" and len(drew) >= 2:
            second_card = drew[1]

            announce(
                r["code"],
                f"{curr['nick']} 블랙 잭 능력: 두 번째 카드 공개 "
                f"({second_card['name']} / {second_card['rank']} {second_card['suit']})"
            )

            if second_card.get("suit") in ("heart", "diamond"):
                bonus = draw_n(r, 1)
                curr["hand"].extend(bonus)
                announce(r["code"], f"{curr['nick']} 블랙 잭 능력 발동! 추가 카드 1장 드로우")

        dm_hand(curr)
        announce(r["code"], f"{curr['nick']} 님의 차례 (카드 가져오기 단계).")

        broadcast_state(r["code"])

def ensure_my_turn(r, sid):
    return r["players"][r["turn_idx"]]["sid"] == sid

def ensure_has_card(p, card_id, ctype=None):
    for i, c in enumerate(p["hand"]):
        if c["id"] == card_id and (ctype is None or c["type"] == ctype):
            return i, c
    return None, None

def can_use_as(card, desired_type, player):
    if card["type"] == desired_type:
        return True

    if player.get("character") == "CALAMITY_JANET":
        if desired_type == "BANG" and card["type"] == "MISSED":
            return True
        if desired_type == "MISSED" and card["type"] == "BANG":
            return True

    return False

# ---------- Steal/Discard helpers (강탈/캣벌로우) ----------
def random_hand_card(p):
    if not p["hand"]:
        return None
    i = random.randrange(len(p["hand"]))
    return i, p["hand"][i]

def list_board_slots(p):
    # 훔치기/버리기 대상이 될 수 있는 장착물 목록(현재 켜진 것만)
    slots = []
    if p["board"].get("barrel"):  slots.append(("barrel",  {"type":"BARREL","name":"BARREL"}))
    if p["board"].get("mustang"): slots.append(("mustang", {"type":"MUSTANG","name":"MUSTANG"}))
    if p["board"].get("scope"):   slots.append(("scope",   {"type":"SCOPE","name":"SCOPE"}))
    wep = p["board"].get("weapon") or "Colt45"
    if wep and wep != "Colt45":
        slots.append(("weapon", {"type":"WEAPON","name":wep,"weapon":wep}))
    # 감옥/다이너마이트는 '버리기'만 가능(훔쳐서 손패로 가지지 않음)
    if p["board"].get("jail"):      slots.append(("jail", {"type":"JAIL","name":"JAIL"}))
    if p["board"].get("dynamite"):  slots.append(("dynamite", {"type":"DYNAMITE","name":"DYNAMITE"}))
    return slots

def remove_board_slot(p, slot):
    # slot: 'barrel'|'mustang'|'scope'|'weapon'|'jail'|'dynamite'
    if slot == "weapon":
        p["board"]["weapon"] = "Colt45"
    else:
        p["board"][slot] = False

# =========================
# 소켓 이벤트
# =========================
@socketio.on("room:create")
def on_room_create(data):
    if request.sid in player_room:
        emit("error", {"message": "이미 방에 참가 중입니다. 새로 만들려면 먼저 나가거나 새로고침하세요."})
        return

    nick = data.get("nick", "Player")
    code = gen_code()
    rooms[code] = {
        "code": code,
        "players": [{"sid": request.sid, "nick": nick, "seat": 0}],
        "spectators": [],
        "host_sid": request.sid,
        "status": "LOBBY",
        "turn_idx": 0,
        "deck": [],
        "discard": [],
        "pending": None,  # 공격 등 대기 상태: {"kind":"ATTACK","attacker":seat,"target":seat}
    }
    player_room[request.sid] = code
    join_room(code)
    emit("room:created", {"code": code, "seat": 0})
    broadcast_state(code)

@socketio.on("room:join")
def on_room_join(data):
    if request.sid in player_room:
        emit("error", {"message": "이미 방에 참가 중입니다."})
        return

    code = (data.get("code") or "").upper()
    nick = data.get("nick", "Player")

    if code not in rooms:
        emit("error", {"message": "방이 없어요."})
        return

    r = rooms[code]

    # 게임 중이면 관전자로 입장
    if r["status"] == "IN_GAME":
        r.setdefault("spectators", []).append({
            "sid": request.sid,
            "nick": nick
        })
        player_room[request.sid] = code
        join_room(code)

        emit("room:joined", {
            "code": code,
            "seat": None,
            "spectator": True
        })

        announce(code, f"{nick} 님이 관전자로 입장했습니다.")
        broadcast_state(code)
        return

    # 대기/종료 상태에서는 플레이어로 입장
    if len(r["players"]) >= 7:
        emit("error", {"message": "최대 7명까지 참여할 수 있습니다."})
        return

    if any(p["nick"] == nick for p in r["players"]):
        emit("error", {"message": "이미 사용 중인 닉네임입니다. 다른 닉네임을 입력하세요."})
        return

    seat = len(r["players"])
    r["players"].append({
        "sid": request.sid,
        "nick": nick,
        "seat": seat
    })

    player_room[request.sid] = code
    join_room(code)

    emit("room:joined", {
        "code": code,
        "seat": seat,
        "spectator": False
    })

    announce(code, f"{nick} 님이 입장했습니다.")
    broadcast_state(code)

@socketio.on("game:start")
def on_game_start():
    code = player_room.get(request.sid)
    if not code: return

    r = rooms.get(code)

    if request.sid != r["host_sid"]:
        emit("error", {"message":"호스트만 시작할 수 있어요."});
        return
    
    if r["status"] == "IN_GAME":
        emit("error", {"message": "이미 게임이 진행 중입니다."})
        return

    if r.get("spectators"):
        for s in r["spectators"]:
            r["players"].append({
                "sid": s["sid"],
                "nick": s["nick"],
                "seat": len(r["players"])
            })

        r["spectators"] = []

    if len(r["players"]) < 4:
        emit("error", {"message":"최소 4명이 필요합니다."})
        return

    if len(r["players"]) > 7:
        emit("error", {"message":"최대 7명까지 플레이할 수 있습니다."})
        return

    # 덱 생성
    r["deck"] = build_deck_basic()
    r["discard"] = []

    ok, msg = assign_roles(r)
    if not ok:
        emit("error", {"message": msg}); return
    
    ok, msg = assign_characters_and_setup(r)
    if not ok:
        emit("error", {"message": msg}); return

    # 보안관 공개 로그
    sheriff = next(p for p in r["players"] if p["role"] == "SHERIFF")
    announce(code, f"보안관은 {sheriff['nick']} 입니다. (보안관만 공개)")

    # 초기 손패
    deal_initial_hands(r, 4)

    # 개인 DM: 역할/캐릭터
    for p in r["players"]:
        dm_role(p)
        dm_character(p)

    r["status"] = "IN_GAME"
    r["turn_idx"] = 0  # 좌석 0부터 시작
    r["pending"] = None
    broadcast_state(code)
    start_turn(r)

@socketio.on("turn:end")
def on_turn_end():
    code, r = get_room_by_sid(request.sid)
    if not r or r["status"] != "IN_GAME": return
    if not ensure_my_turn(r, request.sid):
        emit("error", {"message": "당신의 턴이 아닙니다."}); return
    if r.get("pending"):
        emit("error", {"message": "대기 중인 응답이 끝나야 턴 종료가 가능합니다."}); return

    # 버리기 단계: (MVP) 손패 > HP면 뒤에서 초과분 자동 버림
    me = r["players"][r["turn_idx"]]
    limit = me["hp"]
    if len(me["hand"]) > limit:
        excess = len(me["hand"]) - limit
        auto_discard = me["hand"][-excess:]
        me["hand"] = me["hand"][:-excess]
        discard_cards(r, auto_discard)
        dm_hand(me)
        announce(code, f"{me['nick']} 손패 초과 {excess}장 자동 버림.")

    # 다음 턴
    r["turn_idx"] = next_turn_index(r)
    start_turn(r)

@socketio.on("action:play")
def on_action_play(data):
    """
    { cardId, targetSeat? }
    - BANG: targetSeat 필수, (MVP) 사정거리 1(좌우 인접)만 가능
    - BEER: 자기 HP +1 (MVP: 1:1 제한은 이후)
    - MISSED: 직접 사용 불가(응답 이벤트로만 허용)
    """
    code, r = get_room_by_sid(request.sid)
    if not r or r["status"] != "IN_GAME": return
    if not ensure_my_turn(r, request.sid):
        emit("error", {"message":"당신의 턴이 아닙니다."}); return
    if r.get("pending"):
        emit("error", {"message":"대기 중인 응답이 완료될 때까지 사용할 수 없습니다."}); return

    me = r["players"][r["turn_idx"]]
    idx, card = ensure_has_card(me, data.get("cardId"))
    if card is None:
        emit("error", {"message":"해당 카드는 손패에 없습니다."}); return

    ctype = card["type"]
    if can_use_as(card, "BANG", me):
        if me.get("bang_used") and not has_unlimited_bang(me):
            emit("error", {"message":"이 턴에는 더 이상 뱅!을 사용할 수 없습니다."}); return
        tgt_seat = data.get("targetSeat")
        if tgt_seat is None:
            emit("error", {"message":"대상을 선택하세요."}); return
        # 대상 유효성/거리(인접만)
        targets = [p for p in alive_players(r) if p["seat"] == tgt_seat]
        if not targets:
            emit("error", {"message":"대상이 유효하지 않습니다."}); return
        target = targets[0]
        # 사정거리 검증: dist_with_modifiers ≤ weapon_range
        rng = weapon_range(me["board"].get("weapon"))
        dist = dist_with_modifiers(r, me, target)
        if dist > rng:
            emit("error", {"message":f'사정거리 밖입니다. (거리 {dist}, 무기 사정거리 {rng})'}); return

        # 카드 소모 → 버림
        used = me["hand"].pop(idx)
        discard_cards(r, [used])
        dm_hand(me)

        check_suzy(r, me)

        # 0) 술통(Barrel) 판정: target이 barrel 장착 시 하트면 자동 회피
        if target["board"].get("barrel"):
            revealed = reveal_for_player(r, target, prefer_func=is_heart)

            if is_heart(revealed):
                announce(
                    code,
                    f"{target['nick']} : 🍺 술통 판정 성공! 공격 회피 "
                    f"({revealed['rank']} {revealed['suit']})"
                )
                me["bang_used"] = True
                broadcast_state(code)
                return
            else:
                announce(
                    code,
                    f"{target['nick']} : 🍺 술통 판정 실패 "
                    f"({revealed['rank']} {revealed['suit']})"
                )

        if target.get("character") == "JOURDONNAIS":
            revealed = reveal_for_player(r, target, prefer_func=is_heart)

            if is_heart(revealed):
                announce(
                    code,
                    f"{target['nick']} 주르도네 능력 발동! 하트 판정으로 뱅 회피 "
                    f"({revealed['rank']} {revealed['suit']})"
                )
                me["bang_used"] = True
                broadcast_state(code)
                return
            else:
                if revealed:
                    announce(
                        code,
                        f"{target['nick']} 주르도네 능력 실패 "
                        f"({revealed['rank']} {revealed['suit']})"
                    )
        
        # 1) 공격 대기 상태 설정 및 MISSED 요청
        r["pending"] = {
            "kind": "ATTACK",
            "attacker": me["seat"],
            "target": target["seat"],
            "missed_needed": 2 if me.get("character") == "SLAB_THE_KILLER" else 1,
            "missed_used": 0,
            }
        announce(code, f"{me['nick']} → {target['nick']} : 뱅!")
        # 대상에게 방어 요청
        socketio.emit(
            "prompt:respond",
            {"needs": "MISSED", "count": r["pending"]["missed_needed"]},
            to=target["sid"]
        )
        me["bang_used"] = True
        broadcast_state(code)

    elif ctype == "BEER":
        # 카드 소모
        used = me["hand"].pop(idx)
        discard_cards(r, [used])
        dm_hand(me)
        # 회복 (MVP: 1:1 제한은 이후)
        if me["hp"] < me["max_hp"]:
            me["hp"] += 1
            announce(code, f"{me['nick']} 맥주! (HP {me['hp']}/{me['max_hp']})")
        else:
            announce(code, f"{me['nick']} 맥주 사용(이미 최대 체력).")
        broadcast_state(code)

    elif ctype == "STAGECOACH":
        used = me["hand"].pop(idx)
        discard_cards(r, [used])

        drew = draw_n(r, 2)
        me["hand"].extend(drew)

        dm_hand(me)
        announce(code, f"{me['nick']} 역마차! 카드 2장을 가져옵니다.")
        broadcast_state(code)

    elif ctype == "WELLS_FARGO":
        used = me["hand"].pop(idx)
        discard_cards(r, [used])

        drew = draw_n(r, 3)
        me["hand"].extend(drew)

        dm_hand(me)
        announce(code, f"{me['nick']} 웰스 파고 은행! 카드 3장을 가져옵니다.")
        broadcast_state(code)

    elif ctype == "SALOON":
        used = me["hand"].pop(idx)
        discard_cards(r, [used])
        dm_hand(me)

        healed = []

        for p in alive_players(r):
            if p["hp"] < p["max_hp"]:
                p["hp"] += 1
                healed.append(p["nick"])

        if healed:
            announce(code, f"{me['nick']} 주점! 회복: {', '.join(healed)}")
        else:
            announce(code, f"{me['nick']} 주점! 회복할 플레이어가 없습니다.")

        broadcast_state(code)

    elif ctype == "GENERAL_STORE":
        used = me["hand"].pop(idx)
        discard_cards(r, [used])
        dm_hand(me)

        alive = alive_players(r)
        opened = draw_n(r, len(alive))

        # 사용한 사람부터 시계방향 순서
        ordered = []
        start = me["seat"]
        n = len(r["players"])

        i = start
        while len(ordered) < len(alive):
            p = r["players"][i]
            if p["alive"]:
                ordered.append(p)
            i = (i + 1) % n

        for p, card in zip(ordered, opened):
            p["hand"].append(card)
            dm_hand(p)

        card_names = ", ".join([c["name"] for c in opened])
        announce(code, f"{me['nick']} 잡화점! 공개된 카드: {card_names}")
        announce(code, "잡화점 카드를 시계방향으로 자동 지급했습니다.")

        broadcast_state(code)

    elif ctype == "PANIC":
        # 강탈: 거리 1 이내 대상 지정 필수
        tgt_seat = data.get("targetSeat")
        if tgt_seat is None:
            emit("error", {"message":"강탈 대상이 필요합니다."}); return
        targets = [p for p in alive_players(r) if p["seat"] == tgt_seat]
        if not targets:
            emit("error", {"message":"대상이 유효하지 않습니다."}); return
        target = targets[0]
        # 거리 1(보정 포함)
        if dist_with_modifiers(r, me, target) > 1:
            emit("error", {"message":"강탈은 거리 1에서만 사용할 수 있습니다."}); return
        
        # 사용 카드 소모 → 버림
        used = me["hand"].pop(idx); discard_cards(r, [used]); dm_hand(me)

        # 우선 손패에서 무작위 훔치기, 없으면 보드 장착물 일부를 훔칠 수 있음(무기/술통/야생마/조준경)
        picked = random_hand_card(target)
        if picked is not None:
            ti, tcard = picked
            taken = target["hand"].pop(ti)
            dm_hand(target)
            me["hand"].append(taken)
            dm_hand(me)
            announce(code, f"{me['nick']} ▶ {target['nick']} : 강탈! (손패 1장 훔침)")
        else:
            slots = [s for s in list_board_slots(target) if s[0] in ("weapon","barrel","mustang","scope")]
            if not slots:
                announce(code, f"{me['nick']} ▶ {target['nick']} : 강탈! (훔칠 카드가 없습니다)")
            else:
                slot, proto = random.choice(slots)
                # 보드에서 제거하고 동등 카드(프로토) 손패로 획득
                remove_board_slot(target, slot)
                me["hand"].append({
                    "id": f"SYN-{proto['type']}-{random.randint(1000,9999)}",
                    **proto
                })
                dm_hand(me)
                announce(code, f"{me['nick']} ▶ {target['nick']} : 강탈! ({slot} 장착물 훔침)")
        broadcast_state(code)

    elif ctype == "CATBALOU":
        # 캣 벌로우: 거리 제한 없음, 대상 카드 1장 '버리기'
        tgt_seat = data.get("targetSeat")
        if tgt_seat is None:
            emit("error", {"message":"캣 벌로우 대상이 필요합니다."}); return
        targets = [p for p in alive_players(r) if p["seat"] == tgt_seat]
        if not targets:
            emit("error", {"message":"대상이 유효하지 않습니다."}); return
        target = targets[0]

        # 사용 카드 소모 → 버림
        used = me["hand"].pop(idx); discard_cards(r, [used]); dm_hand(me)

        # 우선 손패에서 무작위 버림, 없으면 보드 장착물 제거(무기/술통/야생마/조준경/감옥/다이너)
        picked = random_hand_card(target)
        if picked is not None:
            ti, tcard = picked
            thrown = target["hand"].pop(ti)
            discard_cards(r, [thrown])
            dm_hand(target)
            announce(code, f"{me['nick']} ▶ {target['nick']} : 캣 벌로우 (손패 1장 버림)")
        else:
            slots = list_board_slots(target)
            if not slots:
                announce(code, f"{me['nick']} ▶ {target['nick']} : 캣 벌로우 (버릴 카드가 없습니다)")
            else:
                slot, proto = random.choice(slots)
                remove_board_slot(target, slot)
                # 버려진 더미에 '프로토'를 가상 카드로 기록(이름만 남김)
                discard_cards(r, [{
                    "id": f"SYN-DISCARD-{proto['type']}-{random.randint(1000,9999)}",
                    **proto
                }])
                announce(code, f"{me['nick']} ▶ {target['nick']} : 캣 벌로우 ({slot} 제거)")
        broadcast_state(code)

    elif ctype == "DUEL":
        tgt_seat = data.get("targetSeat")
        if tgt_seat is None:
            emit("error", {"message":"결투 대상이 필요합니다."}); return
        targets = [p for p in alive_players(r) if p["seat"] == tgt_seat]
        if not targets:
            emit("error", {"message":"대상이 유효하지 않습니다."}); return
        target = targets[0]
        # 카드 소모 → 버림
        used = me["hand"].pop(idx); discard_cards(r, [used]); dm_hand(me)
        set_pending_duel(r, me["seat"], target["seat"])
        broadcast_state(code)

    elif ctype == "INDIANS":
        # 나 외 전원이 BANG 없으면 피해1
        used = me["hand"].pop(idx); discard_cards(r, [used]); dm_hand(me)
        victims = [p["seat"] for p in alive_players(r) if p["sid"] != me["sid"]]
        set_pending_queue(r, "INDIANS", me["seat"], victims, "BANG")
        announce(code, f"{me['nick']} ▶ 인디언! (모두 BANG으로 응수하거나 피해 1)")
        broadcast_state(code)

    elif ctype == "GATLING":
        # 나 외 전원에게 MISS 요구 (술통 가능)
        used = me["hand"].pop(idx); discard_cards(r, [used]); dm_hand(me)
        victims = [p["seat"] for p in alive_players(r) if p["sid"] != me["sid"]]
        set_pending_queue(r, "GATLING", me["seat"], victims, "MISSED")
        announce(code, f"{me['nick']} ▶ 기관총! (모두 Missed!로 막거나 피해 1)")
        broadcast_state(code)

    elif ctype == "WEAPON":
        weapon = (card.get("weapon") or "").upper()
        if weapon not in ("VOLCANIC","SCHOFIELD","REMINGTON","CARBINE","WINCHESTER"):
            emit("error", {"message":"알 수 없는 무기입니다."}); return
        used = me["hand"].pop(idx)
        dm_hand(me)
        old = me["board"].get("weapon") or "Colt45"
        me["board"]["weapon"] = weapon
        announce(code, f"{me['nick']} 🔫 무기 교체: {old} → {weapon}")
        broadcast_state(code)

    elif ctype == "MUSTANG":
        if me["board"].get("mustang"):
            emit("error", {"message":"이미 야생마를 장착했습니다."}); return
        used = me["hand"].pop(idx)
        dm_hand(me)
        me["board"]["mustang"] = True
        announce(code, f"{me['nick']} 🐎 야생마 장착(+1 상대가 나를 볼 때 거리)")
        broadcast_state(code)

    elif ctype == "SCOPE":
        if me["board"].get("scope"):
            emit("error", {"message":"이미 조준경을 장착했습니다."}); return
        used = me["hand"].pop(idx)
        dm_hand(me)
        me["board"]["scope"] = True
        announce(code, f"{me['nick']} 🔭 조준경 장착(-1 내가 남을 볼 때 거리)")
        broadcast_state(code)

    elif ctype == "BARREL":
        # 자기 앞에 술통 장착(중복 금지)
        if me["board"].get("barrel"):
            emit("error", {"message":"이미 술통을 장착 중입니다."}); return
        used = me["hand"].pop(idx)
        dm_hand(me)
        me["board"]["barrel"] = True
        announce(code, f"{me['nick']} 🍺 술통 장착.")
        broadcast_state(code)

    elif ctype == "JAIL":
        tgt_seat = data.get("targetSeat")
        if tgt_seat is None:
            emit("error", {"message":"감옥 대상이 필요합니다."}); return
        targets = [p for p in alive_players(r) if p["seat"] == tgt_seat]
        if not targets:
            emit("error", {"message":"대상이 유효하지 않습니다."}); return
        target = targets[0]
        if target["role"] == "SHERIFF":
            emit("error", {"message":"보안관에게는 감옥을 쓸 수 없습니다."}); return
        if target["board"].get("jail"):
            emit("error", {"message":"해당 대상은 이미 감옥에 있습니다."}); return
        
        used = me["hand"].pop(idx)
        dm_hand(me)
        target["board"]["jail"] = True
        announce(code, f"{target['nick']} 🔒 감옥에 수감되었습니다. (턴 시작 시 판정)")
        broadcast_state(code)

    elif ctype == "DYNAMITE":
        # 방 전체에 이미 다이너마이트가 있는지 체크
        if any(p["board"].get("dynamite") for p in r["players"] if p["alive"]):
            emit("error", {"message":"이미 다이너마이트가 테이블에 있습니다."}); return
        used = me["hand"].pop(idx)
        dm_hand(me)
        me["board"]["dynamite"] = True
        announce(code, f"{me['nick']} 🧨 다이너마이트를 내려놓았습니다. (다음 내 턴부터 판정)")
        broadcast_state(code)

    elif ctype == "MISSED":
        emit("error", {"message":"빗나감!은 방어 응답으로만 사용할 수 있습니다."})
        return

    else:
        emit("error", {"message":"아직 구현되지 않은 카드입니다."})
        return
    
@socketio.on("character:sid_ketchum")
def on_sid_ketchum(data):
    code, r = get_room_by_sid(request.sid)
    if not r or r["status"] != "IN_GAME":
        return

    me = get_player_by_sid(r, request.sid)
    if not me or not me["alive"]:
        return

    if me.get("character") != "SID_KETCHUM":
        emit("error", {"message": "시드 케첨만 사용할 수 있는 능력입니다."})
        return

    if me["hp"] >= me["max_hp"]:
        emit("error", {"message": "이미 최대 체력입니다."})
        return

    card_ids = data.get("cardIds") or []

    if len(card_ids) != 2:
        emit("error", {"message": "카드 2장을 선택해야 합니다."})
        return

    removed = []

    for card_id in card_ids:
        idx, card = ensure_has_card(me, card_id)
        if not card:
            emit("error", {"message": "선택한 카드가 손패에 없습니다."})
            return
        removed.append((idx, card))

    for idx, card in sorted(removed, reverse=True):
        used = me["hand"].pop(idx)
        discard_cards(r, [used])

    me["hp"] += 1
    dm_hand(me)

    announce(code, f"{me['nick']} 시드 케첨 능력 발동! 카드 2장을 버리고 체력 1 회복")
    broadcast_state(code)

@socketio.on("action:respond")
def on_action_respond(data):
    """
    방어/응답 처리:
    - ATTACK: MISSED 제출 또는 포기
    - DUEL: BANG 제출 또는 포기
    - INDIANS: BANG 제출 또는 포기
    - GATLING: MISSED 제출 또는 포기
    """
    code, r = get_room_by_sid(request.sid)
    if not r or r["status"] != "IN_GAME": 
        return
    
    pend = r.get("pending")
    if not pend:
        emit("error", {"message":"대기 중인 응답이 없습니다."})
        return

    kind = pend.get("kind")
    card_id = data.get("cardId")

    # 1. 일반 공격 / 뱅 / 기관총류 단일 공격 응답
    if kind == "ATTACK":
        target_seat = pend["target"]
        target = next((p for p in r["players"] if p["seat"] == target_seat), None)

        if not target or target["sid"] != request.sid:
            emit("error", {"message": "당신에게 온 공격 응답이 아닙니다."})
            return
        
        defended = False

        missed_needed = pend.get("missed_needed", 1)
        missed_used = pend.get("missed_used", 0)

        if card_id:
            idx, card = ensure_has_card(target, card_id)

            if card and can_use_as(card, "MISSED", target):
                used = target["hand"].pop(idx)
                discard_cards(r, [used])
                dm_hand(target)
                check_suzy(r, target)

                missed_used += 1
                pend["missed_used"] = missed_used

                announce(
                    code,
                    f"{target['nick']} 이(가) 빗나감! 제출 "
                    f"({missed_used}/{missed_needed})"
                )

        attacker = next((p for p in r["players"] if p["seat"] == pend["attacker"]), None)

        if missed_used >= missed_needed:
            announce(code, f"{target['nick']} 이(가) 공격 방어에 성공했습니다.")
            r["pending"] = None
            broadcast_state(code)
            return

        if card_id:
            socketio.emit(
                "prompt:respond",
                {"needs": "MISSED", "count": missed_needed - missed_used},
                to=target["sid"]
            )
            broadcast_state(code)
            return

        ended = apply_damage(r, target, 1, source=attacker)
        if ended:
            r["pending"] = None
            return

        r["pending"] = None
        broadcast_state(code)
        return
    
    # 2. 결투 응답
    if kind == "DUEL":
        step_duel(r, request.sid, card_id)
        return
    
    # 3. 인디언 / 기관총 응답
    if kind in ("INDIANS", "GATLING"):
        needs = pend.get("needs")

        if not pend.get("queue"):
            r["pending"] = None
            broadcast_state(code)
            return
        
        seat = pend["queue"][0]
        victim = next((p for p in r["players"] if p["seat"] == seat), None)

        if not victim or victim["sid"] != request.sid:
            emit("error", {"message": "당신 차례의 응답이 아닙니다."})
            return

        defended = False

        if card_id:
            want = "BANG" if needs == "BANG" else "MISSED"
            idx, card = ensure_has_card(victim, card_id)
            if card and can_use_as(card, want, victim):
                used = victim["hand"].pop(idx)
                discard_cards(r, [used])
                dm_hand(victim)
                check_suzy(r, victim)
                defended = True

        if defended:
            announce(code, f"{victim['nick']} : {needs} 제출로 방어.")
        else:
            ended = apply_damage(r, victim, 1, source=None)
            if ended:
                r["pending"] = None
                return
            
        pend["queue"].pop(0)
        _prompt_next_in_queue(r)
        return
    
    emit("error", {"message": "알 수 없는 응답 상태입니다."})

@socketio.on("chat:send")
def on_chat_send(data):
    code = player_room.get(request.sid)
    if not code: return
    r = rooms.get(code)
    nick = next((p["nick"] for p in r["players"] if p["sid"]==request.sid), "Player")
    socketio.emit("chat:append", {"nick": nick, "text": data.get("text","")}, room=code)

@socketio.on("disconnect")
def on_disconnect():
    code = player_room.get(request.sid)
    if not code or code not in rooms: return
    r = rooms[code]
    pidx = next((i for i,p in enumerate(r["players"]) if p["sid"]==request.sid), None)
    if pidx is not None:
        nick = r["players"][pidx]["nick"]
        was_alive = r["players"][pidx].get("alive", True)
        # 로비에서는 완전 제거 / 게임 중에는 (MVP) 즉시 제거로 처리
        if r["status"] == "LOBBY":
            r["players"].pop(pidx)
            for i,p in enumerate(r["players"]): p["seat"] = i
            announce(code, f"{nick} 님이 나갔습니다.")
        else:
            r["players"][pidx]["alive"] = False
            r["players"][pidx]["revealedRole"] = r["players"][pidx]["role"]
            announce(code, f"{nick} 님이 퇴장(제거)되었습니다. 역할: {r['players'][pidx]['role']}")
            check_victory(r)  # 승리 여부 확인

        player_room.pop(request.sid, None)
        if not r["players"]:
            rooms.pop(code, None)
        else:
            # 턴 보정
            if r["status"] == "IN_GAME":
                # 현재 턴 주자가 나갔으면 다음 생존자로 이동
                if r["players"][r["turn_idx"]]["sid"] == request.sid:
                    r["turn_idx"] = next_turn_index(r)
                    if r["status"] == "IN_GAME":
                        start_turn(r)
                        return
            broadcast_state(code)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5173))
    socketio.run(app, host="0.0.0.0", port=port)