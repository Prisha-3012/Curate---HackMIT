from pathlib import Path

from dotenv import load_dotenv

# Repo-root .env even when cwd is apps/api (uvicorn main:app)
_root_env = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_root_env)
load_dotenv()

from fastapi import FastAPI
from routers.sms import router as sms_router

app = FastAPI()
app.include_router(sms_router)


@app.get("/health")
def health():
    return {"ok": True}
