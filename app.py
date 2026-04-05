import streamlit as st
import os
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json
import requests
from datetime import datetime
import logging
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")

st.set_page_config(page_title="MailMind", layout="wide")

st.markdown("""
<style>
    .priority-high { background: linear-gradient(90deg, #dc3545 var(--progress), #e9ecef var(--progress)); }
    .priority-medium { background: linear-gradient(90deg, #ffc107 var(--progress), #e9ecef var(--progress)); }
    .priority-low { background: linear-gradient(90deg, #28a745 var(--progress), #e9ecef var(--progress)); }
    .priority-bar {
        height: 12px;
        border-radius: 6px;
        margin: 10px 0 20px 0;
    }
    .priority-label {
        font-weight: 700;
        font-size: 22px;
        margin-bottom: 6px;
    }
    .priority-high-text { color: #ff4d4d !important; }
    .priority-medium-text { color: #e6a800 !important; }
    .priority-low-text { color: #00cc44 !important; }
    .section-header {
        font-size: 22px;
        font-weight: 700;
        color: #ffffff !important;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 3px solid #444;
    }
    .action-item {
        padding: 12px 16px;
        background: #2a2a2a;
        border-left: 4px solid #3399ff;
        margin: 8px 0;
        border-radius: 0 6px 6px 0;
        font-size: 18px;
        color: #ffffff !important;
    }
    .decision-badge {
        display: inline-block;
        padding: 10px 18px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 18px;
    }
    .decision-reply { background: #28a745; color: #ffffff !important; }
    .decision-ignore { background: #dc3545; color: #ffffff !important; }
    .decision-meeting { background: #007bff; color: #ffffff !important; }
    .summary-text {
        font-size: 18px;
        line-height: 1.6;
        color: #ffffff !important;
    }
    .reply-text {
        font-size: 16px;
        line-height: 1.6;
        color: #e0e0e0 !important;
        background: #2a2a2a;
        padding: 16px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

st.title("MailMind")
st.caption("Email analysis and response automation")

with st.sidebar:
    st.subheader("AI Provider")
    ai_provider = st.radio(
        "Backend",
        ["Gemini (Cloud)", "LM Studio (Local)"],
        label_visibility="collapsed"
    )
    
    if ai_provider == "LM Studio (Local)":
        lm_studio_url = st.text_input("LM Studio URL", value=LM_STUDIO_URL)
    else:
        lm_studio_url = LM_STUDIO_URL
        if not GOOGLE_API_KEY:
            st.warning("Set GOOGLE_API_KEY in .env")
    
    st.divider()
    st.subheader("Automation")
    n8n_enabled = st.checkbox("Enable n8n", value=bool(N8N_WEBHOOK_URL))
    if n8n_enabled:
        n8n_url = st.text_input("Webhook URL", value=N8N_WEBHOOK_URL, type="password")
    else:
        n8n_url = ""

tone = st.selectbox("Response Tone", ["Professional", "Casual", "Assertive"])

email_input = st.text_area("Email Content", height=250, placeholder="Paste email here...")

def send_to_n8n(webhook_url: str, data: dict) -> dict:
    if not webhook_url:
        return {"status": "skipped", "message": "No webhook URL"}
    
    try:
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "source": "mailmind",
            "analysis": data
        }
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        return {"status": "success", "response": response.json() if response.text else {}}
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Timeout"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e)}

def get_prompt(email: str, tone: str) -> str:
    return f"""Analyze the following email and return JSON.

Email:
{email}

Tone: {tone}

Return JSON with these keys:
- "summary" (brief summary)
- "priority" (High / Medium / Low)
- "actions" (list of action items)
- "suggested_reply" (draft reply)
- "decision" (Reply now / Ignore / Schedule meeting)

Return ONLY valid JSON."""


def generate_with_gemini(email: str, tone: str) -> str:
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not configured")
    
    client = genai.Client(api_key=GOOGLE_API_KEY)
    prompt = get_prompt(email, tone)
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.3,
            response_mime_type="application/json",
            system_instruction="You are an executive assistant."
        )
    )
    return response.text


def generate_with_lm_studio(email: str, tone: str, base_url: str) -> str:
    client = OpenAI(base_url=base_url, api_key="lm-studio")
    prompt = get_prompt(email, tone)
    
    response = client.chat.completions.create(
        model="local-model",
        messages=[
            {"role": "system", "content": "You are an executive assistant. Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    content = response.choices[0].message.content
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
    if match:
        return match.group(1)
    return content


def generate_response(email: str, tone: str, provider: str, lm_url: str = "") -> str:
    if provider == "Gemini (Cloud)":
        return generate_with_gemini(email, tone)
    else:
        return generate_with_lm_studio(email, tone, lm_url or LM_STUDIO_URL)


def render_priority(priority: str):
    priority_config = {
        "High": {"progress": "100%", "class": "high"},
        "Medium": {"progress": "60%", "class": "medium"},
        "Low": {"progress": "30%", "class": "low"}
    }
    config = priority_config.get(priority, priority_config["Medium"])
    
    st.markdown(f'<div class="priority-label priority-{config["class"]}-text">{priority}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="priority-bar priority-{config["class"]}" style="--progress: {config["progress"]};"></div>', unsafe_allow_html=True)


def render_decision(decision: str):
    decision_class = "reply" if "Reply" in decision else "ignore" if "Ignore" in decision else "meeting"
    st.markdown(f'<span class="decision-badge decision-{decision_class}">{decision}</span>', unsafe_allow_html=True)


if st.button("Analyze", type="primary"):
    if not email_input.strip():
        st.warning("Enter an email to analyze.")
    elif ai_provider == "Gemini (Cloud)" and not GOOGLE_API_KEY:
        st.error("Set GOOGLE_API_KEY or switch to LM Studio")
    else:
        provider_name = "LM Studio" if "Local" in ai_provider else "Gemini"
        with st.spinner(f"Analyzing..."):
            try:
                result = generate_response(email_input, tone, ai_provider, lm_studio_url)
                data = json.loads(result)

                st.divider()
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown('<div class="section-header">Summary</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="summary-text">{data.get("summary", "N/A")}</div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="section-header">Priority</div>', unsafe_allow_html=True)
                    render_priority(data.get("priority", "Medium"))
                    
                    st.markdown('<div class="section-header">Decision</div>', unsafe_allow_html=True)
                    render_decision(data.get("decision", "N/A"))

                with col2:
                    st.markdown('<div class="section-header">Action Items</div>', unsafe_allow_html=True)
                    actions = data.get("actions", [])
                    if actions:
                        for action in actions:
                            st.markdown(f'<div class="action-item">{action}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="summary-text">No actions required.</div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="section-header">Suggested Reply</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="reply-text">{data.get("suggested_reply", "N/A")}</div>', unsafe_allow_html=True)

                if n8n_enabled and n8n_url:
                    n8n_result = send_to_n8n(n8n_url, data)
                    if n8n_result["status"] == "success":
                        st.success("Sent to n8n")
                    elif n8n_result["status"] == "error":
                        st.warning(f"n8n: {n8n_result['message']}")

                with st.expander("Raw Data"):
                    st.json(data)

            except json.JSONDecodeError:
                st.error("Failed to parse response. Try again.")
            except Exception as e:
                st.error(f"Error: {str(e)}")