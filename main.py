from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "News Alert Bot is running"}

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "News Alert Bot is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

    