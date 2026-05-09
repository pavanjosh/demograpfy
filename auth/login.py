import streamlit as st
from datetime import datetime, timedelta
from auth.bigquery_auth import verify_user
from auth.sessions import create_session, get_session, delete_session
from auth.users import (
    get_or_create_user, reset_usage, should_reset_usage,
    update_last_login, get_usage, get_last_login, get_last_queried,
)
from auth.rbac import get_usage_limit


def _restore_session_from_params():
    """Restore session_state from a persisted session token in query params."""
    if "user" in st.session_state:
        return
    token = st.query_params.get("session")
    if not token:
        return
    session = get_session(token)
    if session:
        st.session_state.user = session["user_id"]
        st.session_state.tier = session["tier"]
        st.session_state.session_token = token
    else:
        # Token is invalid/expired — remove it from the URL
        st.query_params.pop("session", None)


def login_signup():
    _restore_session_from_params()

    # --- IF LOGGED IN: SHOW DASHBOARD ---
    if "user" in st.session_state:
        tier = st.session_state.get("tier", "free")
        user_id = st.session_state.user
        usage = get_usage(user_id)
        limit = get_usage_limit(tier)
        last_login_str = get_last_login(user_id)
        
        # Calculate remaining queries
        remaining = max(0, limit - usage) if limit is not None else None
        
        # Return a dictionary of values to use anywhere in your UI
        return {
            "is_logged_in": True,
            "user_id": user_id,
            "tier": tier,
            "usage": usage,
            "limit": limit,
            "remaining": remaining,
            "last_login": last_login_str
        }
    # --- IF NOT LOGGED IN: SHOW LOGIN FORM ---

    st.markdown("""
        <style>
        [data-testid="stForm"] {
            border-radius: 32px;
            border: 1px solid #e5e7eb;
            padding: 2rem;
            background-color: white;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        }
        </style>
        """, unsafe_allow_html=True)
        
    with st.form("login_form"):
        st.space("medium")
            
        col1, col2, col3 = st.columns([1, 7, 1])  
                
        with col2:

            col11, col12, col13 = st.columns([1, 2, 1])

            with col12:

                st.image("https://www.demografy.com.au/assets/logo-Ds8JU9Fb.svg", width=280)
            
            st.space("xxsmall")
            st.markdown('<p style="background-color: #ede9fe; color: #8b5cf6; display: inline-block; padding: 2px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; letter-spacing: 0.18em; text-transform: uppercase;">● Secure Portal</p>', unsafe_allow_html=True)
            st.header("Welcome Back")
            st.text("Log in to explore growth indicators, shortlist suburbs, and chat with Insight Chatbot.")

            st.space("xsmall")

            input_id = st.text_input("User ID", placeholder="Enter your User ID")
            input_email = st.text_input("Email", placeholder="Enter your email")

            st.space("xxsmall")

            st.markdown("""
        <style>
        /* 1. Base Button Styling */
        div.stFormSubmitButton > button {
            width: 100%;
            border-radius: 12px;
            padding: 0.75rem 1.5rem;
            font-weight: 500;
            color: white;
            background: linear-gradient(#9b72f7 0%, #8b5cf6 100%);
            border: none;
            box-shadow: 0 4px 6px 0 rgba(30, 7, 81, 0.12);
            
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        div.stFormSubmitButton > button:hover {
            box-shadow: 0 8px 15px 0 rgba(30, 7, 81, 0.2);
            transform: scale(1.05); 
            letter-spacing: 0.6px;
        }
        
        div.stFormSubmitButton > button:active {
            transform: scale(0.98); 
        }
        </style>
        """, unsafe_allow_html=True)

            submit = st.form_submit_button("Log in ->", use_container_width=True) 

            st.space("medium")

        if submit:
            user = verify_user(input_id, input_email)
            if user:
                token = create_session(user["user_id"], user["tier"])
                st.session_state.user = user["user_id"]
                st.session_state.tier = user["tier"]
                st.session_state.session_token = token
                st.query_params["session"] = token
                
                get_or_create_user(user["user_id"])
                if should_reset_usage(user["user_id"]): reset_usage(user["user_id"])
                update_last_login(user["user_id"])
                st.rerun()
            else:
                st.error("❌ Invalid User ID or Email credentials.")

    return {"is_logged_in": False}