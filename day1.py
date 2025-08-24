from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from ai_logic import ask_gemini, reset_chat_session
import logging
import os
import json
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("Browser UI connected via WebSocket.")
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        logger.info(f"Broadcasting to {len(self.active_connections)} client(s)...")
        tasks = [connection.send_text(message) for connection in self.active_connections]
        await asyncio.gather(*tasks)

manager = ConnectionManager()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AURA-Server")

app = FastAPI(title="AURA Assistant API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.post("/screenshot_with_prompt")
async def analyze_screenshot_with_prompt(file: UploadFile = File(...), prompt: str = Form(...)):
    try:
        image_data = await file.read()
        ai_response = await ask_gemini(prompt, image_data)

        update_message = { "type": "history_update", "data": {"user": prompt, "ai": ai_response} }
        await manager.broadcast(json.dumps(update_message))

        return JSONResponse({"ai_answer": ai_response})
    except Exception as e:
        return JSONResponse({"error": "Processing failed"}, status_code=500)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/ask")
async def ask_question(question: str, session_id: str = "default"):
    ai_response = await ask_gemini(question, session_id=session_id)
    return JSONResponse({"ai_answer": ai_response})

@app.get("/reset")
def reset_chat(session_id: str = "default"):
    reset_chat_session(session_id)
    return JSONResponse({"status": f"Chat session {session_id} cleared"})