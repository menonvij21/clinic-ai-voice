from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
import requests
import uuid

from voice_agent import think

app = FastAPI()

# -------- CORS --------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- SESSION STORAGE --------
sessions = {}

# -------- HOME --------
@app.get("/")
def home():
    return FileResponse("clinic.html")


# -------- CHAT --------
@app.post("/chat")
async def chat(data: dict):
    message = data.get("message", "")
    session_id = data.get("session_id")

    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = {}

    memory = sessions[session_id]

    response = think(message, memory)

    return {
        "response": response,
        "session_id": session_id
    }


# -------- DEEPGRAM TTS --------
DEEPGRAM_API_KEY = "53e72955216ae33f9d5bebef8849e6a501dc3a61"

@app.post("/speak")
async def speak(data: dict):
    text = data.get("text", "")

    url = "https://api.deepgram.com/v1/speak?model=aura-helios-en"

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json"
    }

    res = requests.post(url, headers=headers, json={"text": text})

    return Response(content=res.content, media_type="audio/mpeg")