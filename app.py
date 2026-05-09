import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import re
from datetime import datetime, timedelta

from agent.memory import ask_question_with_memory, clear_memory
from auth.login import login_signup
from auth.users import get_usage, increment_usage, get_last_queried
from auth.rbac import is_within_limit, get_usage_limit, is_near_limit
from auth.sessions import delete_session


# -------------------------------
# FILE PATHS
# -------------------------------
CHAT_DIR = "chat_history"
os.makedirs(CHAT_DIR, exist_ok=True)


# -------------------------------
# CHAT HISTORY
# -------------------------------
def load_chat(user_id):
    path = f"{CHAT_DIR}/{user_id}.json"
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)


def save_chat(user_id, chat):
    with open(f"{CHAT_DIR}/{user_id}.json", "w") as f:
        json.dump(chat, f)


# -------------------------------
# PARSER
# -------------------------------
def _coerce_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert columns to numeric where >50% of values parse successfully."""
    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().mean() > 0.5:
            df[col] = converted
    return df


def parse_response(text: str) -> pd.DataFrame | None:
    """Extract a DataFrame from the agent's text response.

    Tries, in order:
      1. Markdown table  (| col | col | …)
      2. Numbered/bulleted list with key:value pairs
      3. Legacy rental/social-housing pattern
    """
    # 1. Markdown table
    all_lines = text.splitlines()
    table_lines = [l.strip() for l in all_lines if l.strip().startswith("|")]
    if len(table_lines) >= 2:
        # Drop separator rows like |---|---| or | :---: |
        data_lines = [
            l for l in table_lines
            if not re.fullmatch(r"\|[\s\-|:]+\|", l)
        ]
        if len(data_lines) >= 2:
            try:
                headers = [h.strip() for h in data_lines[0].strip("|").split("|")]
                rows = []
                for row_line in data_lines[1:]:
                    cells = [c.strip() for c in row_line.strip("|").split("|")]
                    # Pad or trim cells to match header count
                    while len(cells) < len(headers):
                        cells.append("")
                    rows.append(dict(zip(headers, cells[:len(headers)])))
                if rows:
                    df = pd.DataFrame(rows)
                    return _coerce_numeric_columns(df)
            except Exception:
                pass

    # 2. Numbered/bulleted list  →  "1. Suburb: 45.3"  or  "- Suburb: 45.3"
    kv_pattern = re.compile(r"^(?:\d+\.|[-*•])\s*(.+?):\s*([\d,.]+)", re.MULTILINE)
    kv_matches = kv_pattern.findall(text)
    if len(kv_matches) >= 2:
        df = pd.DataFrame(kv_matches, columns=["Label", "Value"])
        df["Value"] = pd.to_numeric(df["Value"].str.replace(",", ""), errors="coerce")
        return df.dropna(subset=["Value"]).reset_index(drop=True)

    # 3. Legacy rental / social-housing pattern
    legacy = re.findall(r"(.+): Rental Access ([\d.]+)%, Social Housing ([\d.]+)%", text)
    if legacy:
        df = pd.DataFrame(legacy, columns=["Suburb", "Rental Access (%)", "Social Housing (%)"])
        return _coerce_numeric_columns(df)

    return None


def render_assistant_message(content: str):
    """Render an assistant message: markdown text + dataframe + chart if data found."""
    st.markdown(content)
    df = parse_response(content)
    if df is None or df.empty:
        return

    st.dataframe(df, width="stretch")

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    label_col = df.columns[0]

    if len(numeric_cols) >= 2:
        fig = px.bar(
            df, x=label_col, y=numeric_cols,
            barmode="group", title="Comparison", template="plotly_white",
        )
    elif len(numeric_cols) == 1:
        fig = px.bar(
            df, x=numeric_cols[0], y=label_col,
            orientation="h", title=numeric_cols[0],
            template="plotly_white",
            color=numeric_cols[0], color_continuous_scale="Purples",
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
    else:
        return

    fig.update_layout(margin=dict(t=40, b=20, l=20, r=20), height=350, coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch")


if "clicked_query" not in st.session_state:
    st.session_state.clicked_query = None

def handle_click(query):
    st.session_state.clicked_query = query



# -------------------------------
# MAIN APP
# -------------------------------
st.set_page_config(page_title="Demografy Insight", layout="centered")


login_signup()

if "user" not in st.session_state:
    st.stop()

user_status = login_signup()

if user_status["is_logged_in"]:

    user = user_status["user_id"]
    remaining = user_status["remaining"]
    tier = user_status["tier"]
    usage = user_status["usage"]
    limit = user_status["limit"]
    last_login = user_status["last_login"]

def get_status_color(rem):
        percent = (rem / limit) * 100
        if percent > 70: return "#22c55e"   # Healthy Green
        if percent > 40: return "#f59e0b"   # Warning Orange
        if percent > 15: return "#ef4444"   # Danger Red
        return "#7f1d1d"                   # Critical Dark Red

status_color = get_status_color(remaining)

    # --- 3. CUSTOM UI STYLING ---
st.markdown(f"""
        <style>
        /* Sidebar Metric Card */
        .side-metric {{
            background: white;
            padding: 1rem;
            border-radius: 16px;
            border-left: 10px solid {status_color};
            border-right: 10px solid {status_color};
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            margin-bottom: 1.2rem;
            text-align: center;
        }}
        .metric-label {{ color: #6b7280; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; display:block; margin-bottom:4px; }}
        .metric-value {{ font-size: 1.2rem; font-weight: 800; color: {status_color}; display:block;}}
        
        /* Glossary Cards */
        .glossary-card {{
            background: white;
            padding: 1rem;
            border-radius: 12px;
            border: 1px solid #f3f4f6;
            margin-bottom: 0.75rem;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }}
        .glossary-term {{ color: #8b5cf6; font-weight: 700; font-size: 0.9rem; }}
        .glossary-desc {{ color: #4b5563; font-size: 0.8rem; line-height: 1.4; }}
        </style>
    """, unsafe_allow_html=True)

st.markdown("""
        <style>
        /* Remove huge gaps at the edges of the screen */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 0rem;
            padding-left: 2rem;  
            padding-right: 2rem !important; /* Brings glossary closer to right edge */
            max-width: 100%;
        }
        
        /* Ensure the main app uses full width without forced centering */
        .stMainBlockContainer {
            width: 100% !important;
        }
        </style>
    """, unsafe_allow_html=True)
    # --- 4. SIDEBAR (User Profile, Metrics, & Controls) ---

with st.sidebar:
        # 1. Branding & Animated Status
    st.image("https://www.demografy.com.au/assets/logo-Ds8JU9Fb.svg", width=200)
        
        #limit = TOTAL_LIMIT
        #remaining = limit - used
    pct_used = int((usage / limit) * 100)

        # Dynamic logic for colors
    if pct_used < 50: status_color = "#22c55e" # Green
    elif pct_used < 80: status_color = "#f59e0b" # Orange
    else: status_color = "#ef4444" # Red
    
    st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 20px; margin-top: 20px;">
                <div style="background: #ede9fe; color: #8b5cf6; padding: 4px 12px; border-radius: 20px; font-size: 16px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em;">
                    {tier}
                </div>
                <!-- Progress Bar Container -->
                    
             <div style="display: flex; align-items: center; gap: 10px; border-left: 6px solid {status_color}; padding-left: 10px; height: 20px;">
                    <span style="color: {status_color}; font-size: 12px; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase;">
                        System Status
                    </span>  
            </div>
        """, unsafe_allow_html=True)

    st.space('xsmall')

    if last_login:
        login_dt = datetime.fromisoformat(last_login)
    # Formats to: 30 Apr 2024, 14:30
        last_login_display = f"Last login: {login_dt.strftime('%d %b %Y, %H:%M')}"
    else:
        last_login_display = "First session"
    
    st.markdown(f"""
            <div style="margin-bottom: 24px;">
                <h2 style="margin: 0; font-size: 24px; font-weight: 800; color: #1e1b4b; letter-spacing: -0.02em;">
                    {user}
                </h2>
                <div style="display: flex; align-items: center; gap: 10px; margin-top: 0px;">
                    <div style="width: 12px; height: 1.5px; background: #8b5cf6; opacity: 0.5;"></div>
                    <span style="font-size: 14px; font-weight: 500; color: #64748b; letter-spacing: 0.01em;">
                        {last_login_display}
                    </span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # 2. Premium Metric Card & Gradient Progress Bar
    st.markdown(f"""
            <div style="background: linear-gradient(180deg, #ffffff 0%, #faf5ff 100%); border: 1px solid #e9d5ff; padding: 22px; border-radius: 24px; margin-top: 10px; box-shadow: 0 10px 25px -5px rgba(139, 92, 246, 0.1);">
                <div style="display: flex; justify-content: space-between; align-items: baseline;">
                    <span style="color: #6b7280; font-weight: 600; font-size: 12px; text-transform: uppercase;">Portal Usage</span>
                    <span style="color: #8b5cf6; font-weight: 800; font-size: 24px;">{usage}<small style="color: #a78bfa; font-size: 14px;">/{limit}</small></span>
                </div>
                <div style="background: #f3f4f6; border-radius: 12px; height: 10px; margin-top: 15px; overflow: hidden;">
                    <div style="background: linear-gradient(90deg, #8b5cf6 0%, #d8b4fe {pct_used}%, #f3f4f6 {pct_used}%); height: 100%; transition: width 0.8s ease;"></div>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 8px;">
                    <small style="color: #94a3b8;">{pct_used}% exhausted</small>
                    <small style="color: #94a3b8;">{remaining} left</small>
                </div>
            </div>
        """, unsafe_allow_html=True)
    st.space('xxsmall')
        # 3. High-Visibility Warning (The "Unmissable" Box)
    if pct_used >= 80 and remaining > 0:
        st.markdown(f"""
                <div style="background: #fff1f2; border: 2px solid #fb7185; padding: 16px; border-radius: 16px; margin-top: 10px; position: relative; overflow: hidden;">
                    <div style="position: absolute; top: 0; left: 0; width: 6px; height: 100%; background: #e11d48;"></div>
                    <p style="margin: 0; color: #9f1239; font-weight: 700; font-size: 14px;">⚠️ EXHAUSTION WARNING</p>
                    <p style="margin: 4px 0 0 0; color: #be123c; font-size: 12px; line-height: 1.4;">
                        You have used <b>{usage} of {limit}</b> questions. Your standard research tier credits are nearly exhausted.
                        <b>Reset:</b> 24h from last login.
                    </p>
                </div>
            """, unsafe_allow_html=True)

    st.divider()

        # --- 3. HIGH-READABILITY UPGRADE CARD ---
    if tier.lower() != "pro":
     st.markdown("""
            <div style="background-color: #ffffff; 
                        padding: 16px; 
                        border-radius: 12px; 
                        border: 1px solid #ddd6fe; 
                        border-left: 5px solid #8b5cf6;
                        margin-top: 10px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <p style="margin: 0; font-size: 14px; color: #1e1b4b; font-weight: 800;">
                    🚀 Upgrade to Premium
                </p>
                <div style="margin: 8px 0; height: 1px; background-color: #f3f4f6;"></div>
                <p style="margin: 0; font-size: 12px; color: #4b5563; line-height: 1.5;">
                    Unlock <b>unlimited queries</b>, CSV data exports, and priority suburb analysis.
                </p>
                <p style="margin-top: 10px; font-size: 13px; color: #7c3aed; font-weight: 700;">
                    Contact support to upgrade →
                </p>
            </div>
        """, unsafe_allow_html=True)


    st.space('small')



        # 5. Sidebar Buttons
    if st.button("🗑️ Clear History", width='stretch'):
         # 1. Clear the remote database (calls your existing save function with empty list)
        save_chat(user, [])
        
        # 2. Clear the local session state/variable so the UI updates
        if "chat_history" in st.session_state:
            st.session_state.chat_history = []
        
        # 3. Clear LangChain conversation memory so context doesn't bleed into new chat
        clear_memory(user)

        # 4. Rerun to refresh the chat container
        st.rerun()
            

    if st.button("🚪 Logout", width='stretch'):
        token = st.session_state.get("session_token")
        if token:
            delete_session(token)
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()

 


# --- 5. MAIN CONTENT LAYOUT ---
chat_col, spacer, glossary_col = st.columns([3,0.2, 1.5], gap=None)

with chat_col:
    st.title("💬 Demography Insight Chatbot")
    st.markdown("Your AI assistant for Australian demographic and property trends.")
        
        # Scrollable Chat History
    chat_container = st.container(height=600, border=True)

    with chat_container:
        chat_history = load_chat(user)

        if not chat_history:
            st.info("👋 The chat is empty. Ask me about suburb growth, yields, or demographics!")
        else:
            for msg in chat_history:
                with st.chat_message(msg["role"]):
                    if msg["role"] == "assistant":
                        render_assistant_message(msg["content"])
                    else:
                        st.markdown(msg["content"])

    if remaining>0:
        prompt = st.chat_input("Ask your question...")
        final_prompt = prompt or st.session_state.clicked_query

        if final_prompt:
            st.session_state.clicked_query = None
            chat_history.append({"role": "user", "content": final_prompt})

            with chat_container: # Ensure new messages appear inside the container
                with st.chat_message("user"):
                    st.markdown(final_prompt)
                
                with st.spinner("Analyzing data..."):
                    try:
                        response = ask_question_with_memory(user, final_prompt, chat_history)
                    except Exception as e:
                        st.error(f"Agent error: {e}")
                        st.stop()
                
                with st.chat_message("assistant"):
                    render_assistant_message(str(response))


        # -------------------------------
        # SAVE CHAT & UPDATE USAGE
        # -------------------------------
            chat_history.append({"role": "assistant", "content": str(response)})
            save_chat(user, chat_history)
            increment_usage(user)
            st.rerun()
        
    else:
        last_queried_str = get_last_queried(user)
        if last_queried_str:
            reset_at = datetime.fromisoformat(last_queried_str) + timedelta(hours=24)
            secs_left = max(0, int((reset_at - datetime.now()).total_seconds()))
            hrs, rem = divmod(secs_left, 3600)
            mins, secs = divmod(rem, 60)
            reset_display = f"{hrs}h {mins}m {secs}s"
        else:
            reset_display = "24h"
        st.markdown(f"""
            <div style="background: #FF0000; padding: 8px 12px; border-radius: 8px; margin-top: 10px; text-align: center; display: inline-block; width: 100%;">
                <span style="color: #FFFFFF; font-weight: 700; font-size: 13px; letter-spacing: 0.04em;">🔒 ACCESS LOCKED</span>
                <span style="color: #FFFFFF; font-size: 12px; opacity: 0.9; margin-left: 8px;">Resets in <b>{reset_display}</b></span>
            </div>
        """, unsafe_allow_html=True)




with glossary_col:
    st.markdown("### 🛠️ Resources")
        
        # 1. Demo Queries (Interactive!)
    with st.expander("💡 Sample Questions"):
        st.caption("Click a question to ask it directly:")
        demo_queries = [
                "Top 3 suburbs in Victoria by diversity index ",
                "Average prosperity score in NSW ",
                "Which state has the highest average learning level? ",
                "Suburbs with social housing above 20% ",
                "Most affordable rental suburbs "
            ]
            # Displaying demo queries as code blocks makes them easy to copy-paste

        for query in demo_queries:
            st.button(query, width='stretch', on_click=handle_click, args=(query,))


        # 2. Collapsible Glossary
    with st.expander("📚 Glossary"):
        glossary = {
                "Prosperity Score (kpi_1_val)": "0–100%. Relative advantage of households based on income, occupation, education, and housing.",
                "Diversity Index (kpi_2_val)": "0–1. Cultural diversity based on ancestry. Near 1 is very diverse; near 0 is homogeneous.",
                "Migration Footprint (kpi_3_val)": "0–100%. % of residents with at least one parent born overseas.",
                "Learning Level (kpi_4_val)": "0–100%. % of residents who completed Year 12.",
                "Social Housing (kpi_5_val)": "0–100%. % of public or community housing. High values suggest disadvantage.",
                "Resident Equity (kpi_6_val)": "0–100%. % of dwellings owned outright or with a mortgage.",
                "Rental Access (kpi_7_val)": "0–100%. % of dwellings renting below $450/week. Indicates affordability.",
                "Resident Anchor (kpi_8_val)": "0–100%. % of residents in the same community for 5+ years. Indicates stability.",
                "Household Mobility Potential (kpi_9_val)": "0–1. Households in transitional positions. Indicates potential for change.",
                "Young Family Indicator (kpi_10_val)": "0–100%. % of population aged 0–14. 20%+ is high family presence."
            }

        st.info("Note: Column names use the `kpi_N_val` format (e.g., Prosperity Score is `kpi_1_val`).")

        for term, desc in glossary.items():
            st.markdown(f"**{term}**: {desc}")

        # 3. Pro-Tip Card (Static)
    st.markdown("""
            <div style="background: #ede9fe; padding: 12px; border-radius: 10px; border: 1px solid #8b5cf6;">
                <small style="color: #8b5cf6; font-weight: 700;">PRO TIP</small><br>
                <span style="font-size: 0.8rem; color: #4c1d95;">Ask about specific <b>Suburbs and Index</b> for more accurate yield data.</span>
            </div>
        """, unsafe_allow_html=True)
    