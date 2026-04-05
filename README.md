# MailMind

Email analysis and response automation tool. Analyze emails to extract priorities, action items, and generate suggested replies.

![MailMind Screenshot](assets/screenshot.png)

## Features

- **Email Analysis** - Extract summary, priority level, and action items from emails
- **Response Generation** - Generate suggested replies in different tones (Professional, Casual, Assertive)
- **Priority Visualization** - Color-coded progress bars for priority levels
- **Dual AI Backend** - Switch between Google Gemini (cloud) and LM Studio (local)
- **n8n Integration** - Webhook support for workflow automation
- **REST API** - Programmatic access for integrations

## Quick Start

```bash
# Clone and setup
git clone https://github.com/bhavik-125/mailmind.git
cd mailmind

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API key

# Run
streamlit run app.py
```

## Configuration

Create a `.env` file:

```env
# Google Gemini API (get from https://makersuite.google.com/app/apikey)
GOOGLE_API_KEY=your_api_key

# LM Studio (optional, for local AI)
LM_STUDIO_URL=http://localhost:1234/v1

# n8n webhook (optional)
N8N_WEBHOOK_URL=https://your-n8n.com/webhook/id
```

## Usage

### Web Interface

1. Select AI provider (Gemini or LM Studio)
2. Choose response tone
3. Paste email content
4. Click "Analyze"

### REST API

Start the API server:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Analyze email:

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "email": "Your email content here",
    "tone": "Professional",
    "provider": "gemini"
  }'
```

API Endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/analyze` | POST | Analyze email |
| `/webhook/n8n` | POST | Receive n8n webhooks |

### LM Studio Setup

1. Download [LM Studio](https://lmstudio.ai/)
2. Load a model (Llama, Mistral, Qwen, etc.)
3. Start local server (default port: 1234)
4. Select "LM Studio (Local)" in the app

## Deployment

### Heroku / Railway

```bash
# Uses Procfile automatically
git push heroku main
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
```

## Project Structure

```
mailmind/
├── app.py              # Streamlit web interface
├── api.py              # FastAPI REST endpoints
├── requirements.txt    # Dependencies
├── Procfile           # Deployment config
├── .env.example       # Environment template
└── assets/
    └── screenshot.png # App screenshot
```


