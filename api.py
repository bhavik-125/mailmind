"""
REST API for MailMind - allows n8n to poll/trigger email analysis.
Run with: uvicorn api:app --host 0.0.0.0 --port 8000
"""

import re
from unittest import result

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from openai import OpenAI
import json
import requests
from datetime import datetime

load_dotenv()

app = FastAPI(
    title="MailMind API",
    description="AI-powered email analysis API for n8n integration",
    version="1.0.0"
)

# Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")


class EmailRequest(BaseModel):
    email: str
    tone: str = "Professional"
    provider: Literal["gemini", "lmstudio"] = "gemini"
    lm_studio_url: Optional[str] = None
    send_to_n8n: bool = False
    n8n_webhook_url: Optional[str] = None


class AnalysisResponse(BaseModel):
    summary: str
    priority: str
    actions: list
    suggested_reply: str
    decision: str
    timestamp: str
    provider: str
    n8n_status: Optional[dict] = None


def get_prompt(email: str, tone: str) -> str:
    return f"""Analyze the following email(s) and return a STRICT JSON output.

Email:
{email}

Tone for reply: {tone}

Return JSON with exactly these keys:
- "summary" (short string)
- "priority" (High / Medium / Low)
- "actions" (list of strings representing tasks)
- "suggested_reply" (string based on tone)
- "decision" (Reply now / Ignore / Schedule meeting)

IMPORTANT: Return ONLY valid JSON, no markdown, no explanations."""


def analyze_with_gemini(email: str, tone: str) -> dict:
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not configured")
    
    client = genai.Client(api_key=GOOGLE_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=get_prompt(email, tone),
        config=types.GenerateContentConfig(
            temperature=0.3,
            response_mime_type="application/json",
            system_instruction="You are an AI executive assistant."
        )
    )
    return json.loads(response.text)


def analyze_with_lm_studio(email: str, tone: str, base_url: str) -> dict:
    client = OpenAI(base_url=base_url, api_key="lm-studio")
    prompt = get_prompt(email, tone)

    response = client.chat.completions.create(
        model="local-model",
        messages=[
            {"role": "system", "content": "You are an AI executive assistant. Return ONLY valid JSON, no markdown, no explanations."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    content = response.choices[0].message.content
    
    # Try direct parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Extract JSON from markdown code blocks if present
        import re
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if match:
            return json.loads(match.group(1))
        # Try finding raw JSON object
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            return json.loads(match.group())
        raise ValueError("Could not parse JSON from LM Studio response")


@app.get("/health")
async def health_check():
    """Health check endpoint for deployment monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "providers": {
            "gemini": bool(GOOGLE_API_KEY),
            "lmstudio": LM_STUDIO_URL
        }
    }


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_email(request: EmailRequest):
    """Analyze an email using Gemini or LM Studio."""
    if not request.email.strip():
        raise HTTPException(status_code=400, detail="Email content is required")
    
    try:
        if request.provider == "gemini":
            data = analyze_with_gemini(request.email, request.tone)
        else:
            lm_url = request.lm_studio_url or LM_STUDIO_URL
            data = analyze_with_lm_studio(request.email, request.tone, lm_url)
        
        timestamp = datetime.utcnow().isoformat()
        
        result = AnalysisResponse(
            summary=data.get("summary", ""),
            priority=data.get("priority", "Medium"),
            actions=data.get("actions", []),
            suggested_reply=data.get("suggested_reply", ""),
            decision=data.get("decision", ""),
            timestamp=timestamp,
            provider=request.provider
        )

        if request.send_to_n8n:
            webhook_url = request.n8n_webhook_url or N8N_WEBHOOK_URL
            if webhook_url:
                try:
                    resp = requests.post(
                        webhook_url,
                        json={"timestamp": timestamp, "source": "mailmind-api", "analysis": data},
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
                    result.n8n_status = {"status": "sent", "code": resp.status_code}
                except Exception as e:
                    result.n8n_status = {"status": "error", "message": str(e)}
        
        return result

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse AI response")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/n8n")
async def n8n_webhook(data: dict):
    """Receive webhooks from n8n workflows."""
    return {"received": True, "timestamp": datetime.utcnow().isoformat(), "data": data}
