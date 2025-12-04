"""
Simplified FastAPI Application for Testing
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from datetime import datetime
import os

app = FastAPI(title="Reliability Engineering Demo - Simplified")

@app.get("/")
async def root():
    return {"message": "Reliability Engineering Demo", "version": "2.0", "status": "running"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "redis": "not_checked",
            "database": "not_checked"
        }
    }

@app.get("/api/fast")
async def fast_endpoint():
    return {"data": "fast response", "latency": "< 10ms"}

@app.get("/api/medium")
async def medium_endpoint():
    import asyncio
    await asyncio.sleep(0.05)
    return {"data": "medium response", "latency": "~50ms"}

@app.get("/api/slow")
async def slow_endpoint():
    import asyncio
    await asyncio.sleep(0.2)
    return {"data": "slow response", "latency": "~200ms"}

@app.get("/metrics")
async def metrics():
    return {"metrics": "simplified"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)