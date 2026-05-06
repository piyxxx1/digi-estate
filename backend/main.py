from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from route import gemini

app = FastAPI(title="Ai-Caller Backend")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(gemini.router, prefix="/api/gemini", tags=["gemini"])

@app.get("/")
async def root():
    return {"message": "Ai-Caller Backend is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
