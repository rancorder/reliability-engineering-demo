"""
FastAPI Application - Reliability Engineering Demo
Netflix/Google SRE Level Implementation
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import aioredis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
import os
import logging
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from starlette.responses import Response
import time

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/testdb")

# Prometheus Metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency', ['method', 'endpoint'])
ACTIVE_CONNECTIONS = Gauge('active_connections', 'Number of active connections')
ERROR_COUNT = Counter('errors_total', 'Total errors', ['type'])

# Database Setup
Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True, pool_size=20, max_overflow=40)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Reservation(Base):
    __tablename__ = "reservations"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, index=True, unique=True)
    user_id = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

# Redis Connection Pool
redis_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global redis_pool
    
    # Startup
    logging.info("🚀 Starting application...")
    
    # Initialize Redis
    try:
        redis_pool = await aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50
        )
        logging.info("✅ Redis connected")
    except Exception as e:
        logging.error(f"❌ Redis connection failed: {e}")
        redis_pool = None
    
    # Initialize Database
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logging.info("✅ Database initialized")
    except Exception as e:
        logging.error(f"❌ Database initialization failed: {e}")
    
    yield
    
    # Shutdown
    logging.info("🛑 Shutting down application...")
    if redis_pool:
        await redis_pool.close()
    await engine.dispose()

app = FastAPI(title="Reliability Engineering Demo", lifespan=lifespan)

# Dependency: Database Session
async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

# Dependency: Redis Connection
async def get_redis():
    if redis_pool is None:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return redis_pool

# Middleware: Request Tracking
@app.middleware("http")
async def track_requests(request, call_next):
    ACTIVE_CONNECTIONS.inc()
    start_time = time.time()
    
    try:
        response = await call_next(request)
        
        # Record metrics
        duration = time.time() - start_time
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        return response
    except Exception as e:
        ERROR_COUNT.labels(type=type(e).__name__).inc()
        raise
    finally:
        ACTIVE_CONNECTIONS.dec()

# Health Check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }
    
    # Check Redis
    try:
        if redis_pool:
            await redis_pool.ping()
            health_status["services"]["redis"] = "healthy"
        else:
            health_status["services"]["redis"] = "unavailable"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check Database
    try:
        async with async_session_maker() as session:
            await session.execute("SELECT 1")
            health_status["services"]["database"] = "healthy"
    except Exception as e:
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    return health_status

# Metrics Endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type="text/plain")

# Simple Endpoints for Load Testing
@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Reliability Engineering Demo", "version": "2.0"}

@app.get("/api/fast")
async def fast_endpoint():
    """Fast endpoint (< 10ms)"""
    return {"data": "fast response", "latency": "< 10ms"}

@app.get("/api/medium")
async def medium_endpoint():
    """Medium endpoint (~50ms)"""
    await asyncio.sleep(0.05)
    return {"data": "medium response", "latency": "~50ms"}

@app.get("/api/slow")
async def slow_endpoint():
    """Slow endpoint (~200ms)"""
    await asyncio.sleep(0.2)
    return {"data": "slow response", "latency": "~200ms"}

@app.get("/api/redis/{key}")
async def redis_get(key: str, redis=Depends(get_redis)):
    """Redis GET operation"""
    try:
        value = await redis.get(key)
        if value is None:
            raise HTTPException(status_code=404, detail="Key not found")
        return {"key": key, "value": value}
    except Exception as e:
        ERROR_COUNT.labels(type="redis_error").inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/redis/{key}")
async def redis_set(key: str, value: str, redis=Depends(get_redis)):
    """Redis SET operation"""
    try:
        await redis.set(key, value, ex=300)  # 5 minutes TTL
        return {"key": key, "value": value, "status": "success"}
    except Exception as e:
        ERROR_COUNT.labels(type="redis_error").inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/db/reservations")
async def get_reservations(db: AsyncSession = Depends(get_db)):
    """Get all reservations"""
    from sqlalchemy import select
    
    try:
        result = await db.execute(select(Reservation))
        reservations = result.scalars().all()
        return {
            "count": len(reservations),
            "reservations": [
                {
                    "id": r.id,
                    "room_id": r.room_id,
                    "user_id": r.user_id,
                    "created_at": r.created_at.isoformat()
                }
                for r in reservations
            ]
        }
    except Exception as e:
        ERROR_COUNT.labels(type="database_error").inc()
        raise HTTPException(status_code=500, detail=str(e))

# Concurrent Reservation Endpoint (for Race Condition testing)
@app.post("/api/reserve/{room_id}")
async def reserve_room(room_id: str, user_id: str, db: AsyncSession = Depends(get_db)):
    """
    Reserve a room (Test Race Conditions)
    Only ONE user can reserve the same room
    """
    from sqlalchemy import select
    
    try:
        # Check if room is already reserved
        result = await db.execute(
            select(Reservation).where(
                Reservation.room_id == room_id,
                Reservation.is_active == True
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Room {room_id} already reserved by {existing.user_id}"
            )
        
        # Create reservation
        reservation = Reservation(room_id=room_id, user_id=user_id)
        db.add(reservation)
        await db.commit()
        await db.refresh(reservation)
        
        return {
            "status": "success",
            "room_id": room_id,
            "user_id": user_id,
            "reservation_id": reservation.id
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        ERROR_COUNT.labels(type="reservation_error").inc()
        raise HTTPException(status_code=500, detail=str(e))

# Error simulation endpoints for Chaos Testing
@app.get("/api/chaos/error")
async def simulate_error():
    """Simulate internal server error"""
    ERROR_COUNT.labels(type="simulated_error").inc()
    raise HTTPException(status_code=500, detail="Simulated error for chaos testing")

@app.get("/api/chaos/timeout")
async def simulate_timeout():
    """Simulate timeout (10 seconds)"""
    await asyncio.sleep(10)
    return {"status": "timeout completed"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)