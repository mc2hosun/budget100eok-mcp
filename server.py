"""
100억 가계부 MCP 서버 (1차 / 설계 골격)
- 카카오 PlayMCP 출품용. AI 에이전트가 호출하는 "가계부 도구"들을 제공.
- 표준 MCP(Model Context Protocol) 서버. 우선 FastMCP로 작성.
- 데이터는 SQLite에 사용자별로 저장 (카카오 사용자 식별값은 배포 시 연동 예정).

※ 카카오 클라우드 배포 형식 확인 후, 호스팅/인증 부분만 그 규격에 맞춰 조정합니다.
실행(로컬 테스트): python server.py
"""

import sqlite3
import os
from datetime import datetime
from mcp.server.fastmcp import FastMCP

DB_PATH = os.environ.get("BUDGET_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "budget.db"))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))

INCOME_CATS = ["급여", "용돈", "보너스", "이자/투자", "부수입", "기타수입"]
EXPENSE_CATS = ["식비", "교통", "주거/통신", "생활/마트", "쇼핑", "건강/의료", "문화/여가", "경조사", "기타지출"]
GOAL = 10_000_000_000  # 목표: 100억 원

mcp = FastMCP("100억 가계부", host=HOST, port=PORT)


# ---------- 저장소 ----------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS tx(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT NOT NULL,
        kind TEXT NOT NULL,          -- 'income' | 'expense'
        amount INTEGER NOT NULL,
        category TEXT NOT NULL,
        fixed INTEGER DEFAULT 0,     -- 고정비 여부(지출)
        ymd TEXT NOT NULL,           -- YYYY-MM-DD
        memo TEXT DEFAULT ''
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS budget(
        user TEXT NOT NULL, category TEXT NOT NULL, limit_amt INTEGER NOT NULL,
        PRIMARY KEY(user, category)
    )""")
    return conn


def won(n: int) -> str:
    return f"{n:,}원"


def _uid(user_id: str | None) -> str:
    # 배포 시 카카오 사용자 식별값으로 대체. 지금은 전달값/기본값 사용.
    return user_id or "demo"


# ---------- 도구(tool): AI가 호출 ----------
@mcp.tool()
def record_expense(amount: int, category: str = "기타지출", memo: str = "",
                   date: str = "", fixed: bool = False, user_id: str = "") -> str:
    """지출을 기록한다. 사용자가 '점심 8천원 썼어', '쇼핑 3만원' 처럼 돈을 쓴 것을 말하면 호출.
    amount: 금액(원), category: 분류(식비/교통/쇼핑/경조사 등), fixed: 매달 나가는 고정비면 True."""
    u = _uid(user_id)
    ymd = date or datetime.now().strftime("%Y-%m-%d")
    with db() as conn:
        conn.execute("INSERT INTO tx(user,kind,amount,category,fixed,ymd,memo) VALUES(?,?,?,?,?,?,?)",
                     (u, "expense", int(amount), category, 1 if fixed else 0, ymd, memo))
    return f"✅ 지출 기록: {category} {won(int(amount))} ({ymd}). 100억까지 화이팅이에요! 💪"


@mcp.tool()
def record_income(amount: int, category: str = "기타수입", memo: str = "",
                  date: str = "", user_id: str = "") -> str:
    """수입을 기록한다. 사용자가 '월급 300만원 들어왔어', '용돈 5만원' 처럼 돈이 생긴 것을 말하면 호출."""
    u = _uid(user_id)
    ymd = date or datetime.now().strftime("%Y-%m-%d")
    with db() as conn:
        conn.execute("INSERT INTO tx(user,kind,amount,category,fixed,ymd,memo) VALUES(?,?,?,?,?,?,?)",
                     (u, "income", int(amount), category, 0, ymd, memo))
    return f"💰 수입 기록: {category} {won(int(amount))} ({ymd}). 100억 모으기 한 걸음 더!"


@mcp.tool()
def get_summary(month: str = "", user_id: str = "") -> str:
    """특정 월의 수입·지출·잔액 요약. 사용자가 '이번 달 얼마 썼어?', '잔액 알려줘'라고 하면 호출.
    month: 'YYYY-MM' (비우면 이번 달)."""
    u = _uid(user_id)
    ym = month or datetime.now().strftime("%Y-%m")
    with db() as conn:
        rows = conn.execute("SELECT kind, SUM(amount) FROM tx WHERE user=? AND ymd LIKE ? GROUP BY kind",
                            (u, ym + "%")).fetchall()
    inc = next((r[1] for r in rows if r[0] == "income"), 0) or 0
    exp = next((r[1] for r in rows if r[0] == "expense"), 0) or 0
    bal = inc - exp
    return (f"📊 {ym} 요약\n"
            f"- 수입: {won(inc)}\n- 지출: {won(exp)}\n- 잔액: {won(bal)}")


@mcp.tool()
def analyze_spending(month: str = "", user_id: str = "") -> str:
    """카테고리별 지출 분석 + 고정비/변동비. 사용자가 '어디에 많이 썼어?', '지출 분석해줘'라고 하면 호출."""
    u = _uid(user_id)
    ym = month or datetime.now().strftime("%Y-%m")
    with db() as conn:
        cats = conn.execute("""SELECT category, SUM(amount) FROM tx
                               WHERE user=? AND kind='expense' AND ymd LIKE ?
                               GROUP BY category ORDER BY 2 DESC""", (u, ym + "%")).fetchall()
        fx = conn.execute("""SELECT SUM(CASE WHEN fixed=1 THEN amount ELSE 0 END),
                                    SUM(CASE WHEN fixed=0 THEN amount ELSE 0 END)
                             FROM tx WHERE user=? AND kind='expense' AND ymd LIKE ?""",
                          (u, ym + "%")).fetchone()
    if not cats:
        return f"{ym}에는 아직 지출 내역이 없어요."
    total = sum(c[1] for c in cats)
    lines = [f"📊 {ym} 지출 분석 (총 {won(total)})"]
    for cat, amt in cats:
        pct = round(amt / total * 100) if total else 0
        lines.append(f"- {cat}: {won(amt)} ({pct}%)")
    fixed_amt, var_amt = (fx[0] or 0), (fx[1] or 0)
    lines.append(f"\n고정비 {won(fixed_amt)} · 변동비 {won(var_amt)} (변동비를 줄이면 100억이 빨라져요!)")
    return "\n".join(lines)


@mcp.tool()
def set_budget(category: str, limit: int, user_id: str = "") -> str:
    """카테고리 월 예산 한도를 설정한다. 사용자가 '식비 예산 40만원으로 정해줘'라고 하면 호출."""
    u = _uid(user_id)
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO budget(user,category,limit_amt) VALUES(?,?,?)",
                     (u, category, int(limit)))
    return f"🎯 예산 설정: {category} 월 {won(int(limit))}"


@mcp.tool()
def check_budget(month: str = "", user_id: str = "") -> str:
    """예산 대비 지출 현황과 초과 경고. 사용자가 '예산 얼마나 남았어?', '식비 넘었어?'라고 하면 호출."""
    u = _uid(user_id)
    ym = month or datetime.now().strftime("%Y-%m")
    with db() as conn:
        budgets = conn.execute("SELECT category, limit_amt FROM budget WHERE user=?", (u,)).fetchall()
        if not budgets:
            return "아직 설정된 예산이 없어요. '식비 예산 40만원으로 정해줘'처럼 말해보세요."
        out = [f"🎯 {ym} 예산 현황"]
        for cat, lim in budgets:
            spent = conn.execute("""SELECT COALESCE(SUM(amount),0) FROM tx
                                    WHERE user=? AND kind='expense' AND category=? AND ymd LIKE ?""",
                                 (u, cat, ym + "%")).fetchone()[0]
            pct = round(spent / lim * 100) if lim else 0
            warn = " ⚠️ 초과!" if spent > lim else (" (거의 다 썼어요)" if pct >= 80 else "")
            out.append(f"- {cat}: {won(spent)} / {won(lim)} ({pct}%){warn}")
    return "\n".join(out)


@mcp.tool()
def goal_progress(user_id: str = "") -> str:
    """목표 100억까지의 진행률을 응원과 함께 알려준다. 사용자가 '100억까지 얼마 남았어?'라고 하면 호출.
    (현재 순자산 = 전체 수입 - 전체 지출 기준)"""
    u = _uid(user_id)
    with db() as conn:
        inc = conn.execute("SELECT COALESCE(SUM(amount),0) FROM tx WHERE user=? AND kind='income'", (u,)).fetchone()[0]
        exp = conn.execute("SELECT COALESCE(SUM(amount),0) FROM tx WHERE user=? AND kind='expense'", (u,)).fetchone()[0]
    net = inc - exp
    pct = net / GOAL * 100
    remain = max(GOAL - net, 0)
    bar = "■" * int(min(pct, 100) // 5) + "□" * (20 - int(min(pct, 100) // 5))
    return (f"🎯 100억 부자 진행률\n[{bar}] {pct:.4f}%\n"
            f"- 현재: {won(net)}\n- 남은 금액: {won(remain)}\n"
            f"여러분, 100억 부자되세요! — MC2호선 응원 중 💛")


@mcp.tool()
def list_transactions(month: str = "", category: str = "", user_id: str = "") -> str:
    """최근 거래 내역을 조회한다. 사용자가 '이번 달 경조사 내역 보여줘'처럼 특정 분류/기간을 물으면 호출."""
    u = _uid(user_id)
    ym = month or datetime.now().strftime("%Y-%m")
    q = "SELECT ymd, kind, category, amount, memo FROM tx WHERE user=? AND ymd LIKE ?"
    args = [u, ym + "%"]
    if category:
        q += " AND category=?"; args.append(category)
    q += " ORDER BY ymd DESC, id DESC LIMIT 30"
    with db() as conn:
        rows = conn.execute(q, args).fetchall()
    if not rows:
        return "해당 내역이 없어요."
    out = [f"🧾 {ym} 내역" + (f" · {category}" if category else "")]
    for ymd, kind, cat, amt, memo in rows:
        sign = "+" if kind == "income" else "−"
        out.append(f"- {ymd[5:]} {cat} {sign}{won(amt)}" + (f" ({memo})" if memo else ""))
    return "\n".join(out)


if __name__ == "__main__":
    # 원격(HTTP) 전송. PlayMCP Endpoint = http(s)://<host>/mcp
    mcp.run(transport="streamable-http")
