"""Streamlit chat UI: chat on the left, live account canvas on the right. OWNER: C.
Run: streamlit run app/streamlit_app.py
"""
import html
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for Streamlit Cloud

# Chroma needs SQLite >= 3.35; Streamlit Cloud's system SQLite can be older. On Linux,
# requirements.txt installs pysqlite3-binary and we swap it in. Locally this is a no-op.
try:
    import pysqlite3  # noqa: F401

    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
try:  # Streamlit Community Cloud secrets; locally there's usually no secrets.toml
    os.environ.setdefault("ANTHROPIC_API_KEY", st.secrets["ANTHROPIC_API_KEY"])
    os.environ.setdefault("CLAUDE_MODEL", st.secrets.get("CLAUDE_MODEL", "claude-haiku-5-5"))
except Exception:
    pass

from agent.agent import respond  # noqa: E402
from agent.escalation import list_cases  # noqa: E402
from contracts import AgentResponse, MarginStatus  # noqa: E402
from engine.margin import liquidation_distance, margin_status  # noqa: E402

st.set_page_config(page_title="Margin Risk Assistant", layout="wide", initial_sidebar_state="collapsed")

# Healthy, past the 48h clock, inside the 48h clock, below soft edge. See the README's demo table.
ACCOUNTS = {
    "M-001": "Healthy",
    "M-003": "Below maint. >48h",
    "M-006": "Below maint. <48h",
    "M-008": "Below soft edge",
}
ACCOUNT_TOOLS = {"margin_status", "liquidation_distance", "weekend_risk_check", "escalate_to_risk_desk"}
QUICK_ACTIONS = [
    (":material/monitoring: Review margin details", "Explain my current margin position in detail."),
    (":material/event: Check weekend risk", "It's Friday. Is my account at risk over the weekend?"),
    (":material/support_agent: Talk to a human", "I'd like to speak to a human about my account."),
]
STATUS = {  # label, colour
    "healthy": ("Healthy", "#22c55e"),
    "below_mm": ("Below maintenance", "#f59e0b"),
    "below_se": ("Below soft edge", "#ef4444"),
}
RISK = {
    "none": ("None", "#22c55e"),
    "after_48h": ("After 48h", "#f59e0b"),
    "anytime": ("Any time", "#ef4444"),
    "immediate": ("Immediate", "#ef4444"),
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, .stApp, .stMarkdown, button, input, textarea { font-family: 'Inter', sans-serif; }
.stApp { background: radial-gradient(1100px 600px at 15% -10%, #1b2446 0%, #0b1020 55%); }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 0.8rem; padding-bottom: 1rem; max-width: 1560px; }
div[data-testid="stColumn"]:has(.pane-chat), div[data-testid="stColumn"]:has(.pane-canvas) {
  background: rgba(18, 26, 46, .72); border: 1px solid #222d48; border-radius: 18px; padding: 18px 20px; }
.hdr { display: flex; align-items: center; gap: 14px; }
.avatar { width: 38px; height: 38px; flex: none; border-radius: 50%; background: linear-gradient(135deg,#ff7a1a,#ffb067);
  display: flex; align-items: center; justify-content: center; font-weight: 700; color: #1a1205; font-size: 17px; }
.hdr h2 { margin: 0; font-size: 21px; font-weight: 700; color: #f2f4f8; }
.pill { display: inline-flex; align-items: center; gap: 6px; margin-top: 0; padding: 3px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 600; background: rgba(34,197,94,.12); color: #4ade80; border: 1px solid rgba(34,197,94,.35); }
.pill .dot { width: 7px; height: 7px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 8px #22c55e; }
.title { font-size: 21px; font-weight: 700; color: #f2f4f8; margin: 0 0 2px; }
.sub { font-size: 12px; color: #8e9ab3; margin-bottom: 12px; }
.card { background: #141d33; border: 1px solid #25304c; border-radius: 14px; padding: 12px 15px; margin-bottom: 12px; }
.card h4 { margin: 0 0 10px; font-size: 14.5px; font-weight: 600; color: #e8ecf4; }
.zone { display: flex; height: 38px; border-radius: 9px; overflow: hidden; position: relative; font-size: 13px; font-weight: 700; }
.zone div { display: flex; align-items: center; padding-left: 10px; color: #0b1020; white-space: nowrap; overflow: hidden; }
.marker { position: absolute; top: -6px; bottom: -6px; width: 3px; background: #fff; border-radius: 2px; box-shadow: 0 0 10px #fff; }
.zlabels { display: flex; justify-content: space-between; font-size: 11.5px; margin-top: 2px; color: #8e9ab3; }
.bento { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.tile { border-radius: 12px; padding: 9px 12px; border: 1px solid #2a3554; background: #182241; }
.tile .k { font-size: 12px; color: #aab4cb; display: flex; justify-content: space-between; align-items: center; }
.tile .v { font-size: 19px; font-weight: 700; margin-top: 4px; color: #f2f4f8; }
.tile .n { font-size: 11.5px; color: #8e9ab3; margin-top: 2px; }
.badge { white-space: nowrap; font-size: 10.5px; font-weight: 700; padding: 2px 7px; border-radius: 6px; }
.pos { display: flex; justify-content: space-between; font-size: 12.5px; padding: 7px 0; border-top: 1px solid #222d48; color: #cdd5e6; }
.pos:first-child { border-top: 0; }
.metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; margin-top: 10px; border: 1px solid #2a3554;
  border-radius: 12px; overflow: hidden; background: #131b30; }
.metrics div { padding: 9px 12px; border-left: 1px solid #2a3554; }
.metrics div:first-child { border-left: 0; }
.metrics span { display: block; font-size: 11.5px; color: #8e9ab3; }
.metrics b { font-size: 16px; color: #f2f4f8; }
.esc { margin-top: 10px; padding: 10px 14px; border-radius: 12px; background: rgba(255,122,26,.12);
  border: 1px solid rgba(255,122,26,.45); font-size: 13.5px; color: #ffd2b0; }
.src a { color: #ffb067; text-decoration: none; }
.src li { margin-bottom: 7px; font-size: 13px; color: #cdd5e6; }
.muted { color: #8e9ab3; font-size: 12.5px; }
.foot { color: #6f7a94; font-size: 11.5px; margin-top: 6px; }
div[data-testid="stChatMessage"] { background: transparent; }
.st-key-chatbox, div:has(> .st-key-chatbox) { height: calc(100vh - 322px) !important; max-height: none !important; min-height: 420px; flex: 0 0 auto !important; }
.st-key-quick button { padding: 2px 10px; min-height: 34px; font-size: 13px; border-radius: 999px; }
.foot { margin-top: 2px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def md(text: str) -> str:
    """Escape $ so Streamlit doesn't treat "$1,137.40 ... $1,241.22" as a LaTeX formula."""
    return text.replace("$", r"\$")


def money(x: float) -> str:
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


def pct(x: float) -> str:
    return f"{x:.0%}" if abs(x - round(x, 2)) < 1e-9 else f"{x:.1%}"


# ---------- state ----------
st.sidebar.markdown("**Demo controls**")
show_trace = st.sidebar.toggle("Show how the agent answered", value=True)

if "account_id" not in st.session_state:
    st.session_state.account_id = "M-003"
if "turns" not in st.session_state:
    st.session_state.turns, st.session_state.api_messages = [], []  # turns: (role, text, AgentResponse|None, snapshot|None)


def _reset_chat() -> None:
    st.session_state.turns, st.session_state.api_messages = [], []


def _queue(prompt: str) -> None:
    st.session_state.pending = prompt


# ---------- layout ----------
left, right = st.columns([1.12, 1], gap="large")

with left:
    st.markdown('<span class="pane-chat"></span>', unsafe_allow_html=True)
    head, pick = st.columns([3, 2.2], vertical_alignment="center")
    with pick:
        account_id = st.selectbox(
            "Demo account", list(ACCOUNTS), key="account_id", on_change=_reset_chat,
            format_func=lambda a: f"{a} · {ACCOUNTS[a]}", label_visibility="collapsed",
        )
    with head:
        st.markdown(
            f"""<div class="hdr"><div class="avatar">MR</div><div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><h2>Margin Risk Assistant</h2>
            <span class="pill"><span class="dot"></span>Demo account {account_id} connected</span></div></div>""",
            unsafe_allow_html=True,
        )

    status_now = margin_status(account_id)

    def metrics_strip(s: dict) -> str:
        cells = [("Equity", s["equity"]), ("Market value", s["market_value"]),
                 ("Margin loan", s["margin_loan"]), ("Maintenance req.", s["mm_req"])]
        return '<div class="metrics">' + "".join(f"<div><span>{k}</span><b>{money(v)}</b></div>" for k, v in cells) + "</div>"

    def render_extras(response: AgentResponse, snapshot: dict | None) -> None:
        if snapshot:
            st.markdown(metrics_strip(snapshot), unsafe_allow_html=True)
        if response.case_summary:
            case = response.case_summary
            st.markdown(
                f'<div class="esc">⚑ Escalated to the human risk desk · case <b>{html.escape(case["case_id"])}</b> · '
                f'{html.escape(case["reason"].replace("_", " "))}</div>', unsafe_allow_html=True)
            if show_trace:
                with st.expander("Case sent to the risk desk"):
                    st.json(case)
        if show_trace and response.tools_called:
            with st.expander(f"Tools called ({len(response.tools_called)})"):
                for call in response.tools_called:
                    st.markdown(f"`{call['name']}` · {'error' if call['is_error'] else 'ok'}")
                    st.json({"input": call["input"], "output": call["output"]}, expanded=False)

    chat = st.container(height=500, border=False, key="chatbox")
    with chat:
        if not st.session_state.turns:
            st.markdown(
                '<div class="muted" style="padding:28px 6px">Ask about your margin, for example '
                '<b>"Am I going to get liquidated?"</b> The figures on the right come straight from the margin engine.</div>',
                unsafe_allow_html=True)
        for role, text, response, snapshot in st.session_state.turns:
            with st.chat_message(role, avatar=":material/person:" if role == "user" else ":material/shield:"):
                st.markdown(md(text))
                if response is not None:
                    render_extras(response, snapshot)

    if st.session_state.turns:
        with st.container(key="quick"):
            cols = st.columns(len(QUICK_ACTIONS), gap="small")
            for col, (label, text) in zip(cols, QUICK_ACTIONS):
                col.button(label, on_click=_queue, args=(text,), use_container_width=True)
    prompt = st.chat_input("Ask about your margin, e.g. 'Am I going to get liquidated?'")
    prompt = prompt or st.session_state.pop("pending", None)
    if prompt:
        st.session_state.turns.append(("user", prompt, None, None))
        st.session_state.api_messages.append({"role": "user", "content": prompt})
        with chat:
            with st.chat_message("user", avatar=":material/person:"):
                st.markdown(md(prompt))
            with st.chat_message("assistant", avatar=":material/shield:"):
                with st.spinner("Checking your account..."):
                    try:
                        response = respond(st.session_state.api_messages, account_id)
                    except Exception as e:  # show API/config errors instead of a blank page
                        st.error(f"The assistant hit an error: {e}")
                        st.session_state.api_messages.pop()
                        st.session_state.turns.pop()
                        st.stop()
        used = {c["name"] for c in response.tools_called if not c["is_error"]}
        snap = vars(margin_status(account_id)) if used & ACCOUNT_TOOLS else None
        st.session_state.turns.append(("assistant", response.answer, response, snap))
        st.rerun()

    st.markdown(f'<div class="foot">🔒 {account_id} · demo data · saved price snapshot · assumed margin ratios · '
                'not investment advice · not affiliated with moomoo</div>', unsafe_allow_html=True)


# ---------- canvas ----------
def zone_bar(s: MarginStatus) -> str:
    scale = max(s.mm_req * 1.35, s.equity * 1.15, 1.0)
    red, amber = s.se_req / scale, (s.mm_req - s.se_req) / scale
    green = max(0.0, 1 - red - amber)
    pos = min(max(s.equity / scale, 0.0), 1.0)
    return f"""<div class="zone">
      <div style="width:{red:.1%};background:#ef4444">Liquidation</div>
      <div style="width:{amber:.1%};background:#f59e0b">Below maint.</div>
      <div style="width:{green:.1%};background:#22c55e">Healthy</div>
      <span class="marker" style="left:calc({pos:.1%} - 1px)"></span></div>
      <div style="position:relative;height:18px;margin-top:5px">
        <span style="position:absolute;left:{pos:.1%};transform:translateX(-{pos:.0%});white-space:nowrap;
        font-size:12px;font-weight:700;color:#fff">▲ Equity {money(s.equity)}</span></div>
      <div class="zlabels"><span style="color:#fca5a5">Soft edge {money(s.se_req)}</span>
      <span style="color:#fcd34d">Maintenance {money(s.mm_req)}</span></div>"""


def tile(key: str, value: str, note: str = "", badge: tuple[str, str] | None = None, tone: str | None = None) -> str:
    border = {"red": "#7f1d1d", "amber": "#78350f", "green": "#14532d"}.get(tone or "", "#2a3554")
    bg = {"red": "#2a1420", "amber": "#2a2014", "green": "#12261f"}.get(tone or "", "#182241")
    b = f'<span class="badge" style="background:{badge[1]}22;color:{badge[1]}">{badge[0]}</span>' if badge else ""
    return (f'<div class="tile" style="border-color:{border};background:{bg}"><div class="k">{key}{b}</div>'
            f'<div class="v">{value}</div><div class="n">{note}</div></div>')


def gauge(s: MarginStatus) -> str:
    cover = s.equity / s.mm_req if s.mm_req else 1.5
    t = min(max(cover, 0.0), 1.5) / 1.5  # 0..1 across the dial
    se_t = (s.se_req / s.mm_req) / 1.5 if s.mm_req else 0.0
    import math

    def pt(frac: float, r: float) -> tuple[float, float]:
        a = math.pi * (1 - frac)
        return 110 + r * math.cos(a), 110 - r * math.sin(a)

    def arc(f0: float, f1: float, color: str) -> str:
        (x0, y0), (x1, y1) = pt(f0, 88), pt(f1, 88)
        return f'<path d="M{x0:.1f},{y0:.1f} A88,88 0 0,1 {x1:.1f},{y1:.1f}" stroke="{color}" stroke-width="16" fill="none"/>'

    nx, ny = pt(t, 70)
    cover_text = ("Equity is <b>negative</b>: the loan exceeds the holdings" if s.equity < 0
                  else f"Equity is <b>{cover:.0%}</b> of maintenance")
    label, color = STATUS[s.status]
    return f"""<svg viewBox="0 0 220 135" width="100%" style="max-width:230px;display:block;margin:auto">
      {arc(0, se_t, '#ef4444')}{arc(se_t, 1 / 1.5, '#f59e0b')}{arc(1 / 1.5, 1, '#22c55e')}
      <line x1="110" y1="110" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#f2f4f8" stroke-width="4" stroke-linecap="round"/>
      <circle cx="110" cy="110" r="7" fill="#f2f4f8"/>
      <text x="110" y="132" text-anchor="middle" font-size="13" font-weight="700" fill="{color}">{label}</text></svg>
      <div style="text-align:center;font-size:13px;color:#cdd5e6;margin-top:4px">{cover_text}</div>"""


with right:
    s = margin_status(account_id)
    dist = liquidation_distance(account_id)
    st.markdown('<span class="pane-canvas"></span>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="title">My Account Canvas</div><div class="sub">{s.currency} · prices from the saved snapshot · '
        f'{s.as_of:%a %d %b %H:%M} UTC · margin ratios are documented assumptions</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="card"><h4>Margin zones</h4>{zone_bar(s)}</div>', unsafe_allow_html=True)

    gap = s.equity - s.mm_req
    if s.hours_below_mm is None:
        hours = tile("Time below maintenance", "Unknown", "start not recorded", ("Any time", "#ef4444"), "red")
    elif s.status == "healthy":
        hours = tile("Time below maintenance", "—", "not below maintenance", None, "green")
    else:
        over = s.hours_below_mm >= 48
        hours = tile("Time below maintenance", f"{s.hours_below_mm:,.0f} h",
                     "past the 48-hour rule" if over else "48-hour clock running",
                     ("> 48h" if over else "< 48h", "#ef4444" if over else "#f59e0b"), "red" if over else "amber")
    risk_label, risk_color = RISK[s.liquidation_risk]
    tiles = [
        tile("Equity", money(s.equity), f"{money(gap)} vs maintenance" if gap < 0 else f"+{money(gap)} above maintenance",
             ("below" if gap < 0 else "ok", "#ef4444" if gap < 0 else "#22c55e"), "red" if gap < 0 else "green"),
        tile("Maintenance requirement", money(s.mm_req), "liquidation after 48h below this"),
        tile("Soft-edge requirement", money(s.se_req), "liquidation can be immediate below this",
             ("breached", "#ef4444") if s.status == "below_se" else None, "red" if s.status == "below_se" else None),
        tile("Margin loan", money(s.margin_loan), f"market value {money(s.market_value)} · cash {money(s.cash)}"),
        hours,
        tile("Liquidation risk", risk_label, "from the engine's rules", None,
             {"none": "green", "after_48h": "amber"}.get(s.liquidation_risk, "red")),
    ]
    st.markdown(f'<div class="card"><h4>Account snapshot</h4><div class="bento">{"".join(tiles)}</div></div>',
                unsafe_allow_html=True)

    g, d = st.columns(2, gap="small")
    with g:
        st.markdown(f'<div class="card"><h4>Account health</h4>{gauge(s)}</div>', unsafe_allow_html=True)
    with d:
        rows = "".join(
            f'<div class="pos"><span><b>{p.ticker}</b> × {p.quantity:g} @ {money(p.price)}'
            f'<br><span class="muted">maint. {pct(p.maintenance_ratio)} · soft edge {pct(p.soft_edge_ratio)}</span></span>'
            f'<b>{money(p.market_value)}</b></div>'
            for p in s.positions)
        drop = ("already below" if dist.pct_drop_to_mm == 0 else f"{dist.pct_drop_to_mm:.1%} drop")
        drop_se = ("already below" if dist.pct_drop_to_se == 0 else f"{dist.pct_drop_to_se:.1%} drop")
        st.markdown(
            f'<div class="card"><h4>Positions & distance to liquidation</h4>{rows}'
            f'<div class="pos"><span>To maintenance</span><b>{drop}</b></div>'
            f'<div class="pos"><span>To soft edge</span><b>{drop_se}</b></div></div>', unsafe_allow_html=True)

    last = next((r for role, _, r, _ in reversed(st.session_state.turns) if role == "assistant" and r), None)
    if last and last.citations:
        items = "".join(f'<li><a href="{html.escape(c["url"])}" target="_blank">{html.escape(c["title"])}</a></li>'
                        for c in last.citations)
        sources = f'<ul class="src" style="padding-left:18px;margin:0">{items}</ul>'
    else:
        sources = '<div class="muted">The help-centre pages behind the latest answer appear here.</div>'
    cases = list_cases(account_id)
    case_html = (f'<div class="muted" style="margin-top:10px">Risk desk cases: <b style="color:#ffb067">{len(cases)}</b>'
                 + (f' · latest {html.escape(cases[0]["case_id"])} ({html.escape(cases[0]["reason"].replace("_", " "))})' if cases else "")
                 + "</div>")
    st.markdown(f'<div class="card"><h4>Source citations</h4>{sources}{case_html}</div>', unsafe_allow_html=True)
