"""
Redis Distributed Lock Tests
Netflix/Google SRE Level - Distributed Locking Patterns

Purpose: Test distributed locking mechanisms for concurrent operations
"""
import pytest
import asyncio
import aioredis
import os
import time
from typing import List, Optional
import uuid

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

class RedisDistributedLock:
    """
    Distributed Lock Implementation using Redis
    Based on Redis SETNX pattern
    """
    
    def __init__(self, redis_client: aioredis.Redis, lock_key: str, timeout: int = 10):
        self.redis = redis_client
        self.lock_key = f"lock:{lock_key}"
        self.timeout = timeout
        self.lock_value = str(uuid.uuid4())
        self.acquired = False
    
    async def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Acquire distributed lock
        
        Args:
            blocking: If True, wait until lock is available
            timeout: Maximum time to wait for lock (only if blocking=True)
        
        Returns:
            True if lock acquired, False otherwise
        """
        start_time = time.time()
        
        while True:
            # Try to acquire lock with SETNX (SET if Not eXists)
            acquired = await self.redis.set(
                self.lock_key,
                self.lock_value,
                ex=self.timeout,  # Auto-expire after timeout
                nx=True  # Only set if key doesn't exist
            )
            
            if acquired:
                self.acquired = True
                return True
            
            if not blocking:
                return False
            
            # Check timeout
            if timeout and (time.time() - start_time) >= timeout:
                return False
            
            # Wait a bit before retrying
            await asyncio.sleep(0.01)
    
    async def release(self):
        """Release distributed lock"""
        if not self.acquired:
            return
        
        # Use Lua script to ensure we only delete our own lock
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        await self.redis.eval(lua_script, 1, self.lock_key, self.lock_value)
        self.acquired = False
    
    async def __aenter__(self):
        """Context manager entry"""
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.release()

@pytest.mark.asyncio
async def test_basic_distributed_lock():
    """
    Test: Basic distributed lock acquisition and release
    Expected: Lock can be acquired and released successfully
    """
    redis = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    
    try:
        lock = RedisDistributedLock(redis, "test_lock_1")
        
        # Acquire lock
        acquired = await lock.acquire(blocking=False)
        assert acquired, "Failed to acquire lock"
        
        # Try to acquire same lock (should fail)
        lock2 = RedisDistributedLock(redis, "test_lock_1")
        acquired2 = await lock2.acquire(blocking=False)
        assert not acquired2, "Second lock should not be acquired"
        
        # Release lock
        await lock.release()
        
        # Now second lock should succeed
        acquired3 = await lock2.acquire(blocking=False)
        assert acquired3, "Lock should be acquirable after release"
        await lock2.release()
        
        print("✅ PASS: Basic distributed lock works correctly")
        
    finally:
        await redis.close()

@pytest.mark.asyncio
async def test_concurrent_lock_acquisition():
    """
    Test: 100 tasks try to acquire the same lock
    Expected: Only one task holds the lock at any time
    """
    redis = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    
    num_tasks = 100
    shared_counter = {"value": 0}
    lock_holders = []
    
    async def worker(worker_id: int):
        """Worker that increments counter with lock protection"""
        lock = RedisDistributedLock(redis, "counter_lock", timeout=5)
        
        async with lock:
            # Critical section
            current = shared_counter["value"]
            lock_holders.append(worker_id)
            await asyncio.sleep(0.01)  # Simulate work
            shared_counter["value"] = current + 1
    
    try:
        # Execute all workers concurrently
        tasks = [worker(i) for i in range(num_tasks)]
        await asyncio.gather(*tasks)
        
        print("\n" + "="*60)
        print("🔒 Concurrent Lock Acquisition Test")
        print("="*60)
        print(f"Expected Counter:      {num_tasks}")
        print(f"Actual Counter:        {shared_counter['value']}")
        print(f"Lock Acquisitions:     {len(lock_holders)}")
        print("="*60)
        
        # Verify counter is exactly num_tasks (no lost updates)
        assert shared_counter["value"] == num_tasks, \
            f"❌ Lost updates detected! Expected {num_tasks}, got {shared_counter['value']}"
        
        assert len(lock_holders) == num_tasks, \
            "❌ Not all workers acquired lock"
        
        print("✅ PASS: All workers successfully acquired lock sequentially")
        
    finally:
        await redis.close()

@pytest.mark.asyncio
async def test_lock_timeout_and_auto_release():
    """
    Test: Lock auto-expires after timeout
    Expected: Lock is automatically released after timeout period
    """
    redis = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    
    try:
        # Acquire lock with 2-second timeout
        lock1 = RedisDistributedLock(redis, "timeout_lock", timeout=2)
        acquired = await lock1.acquire(blocking=False)
        assert acquired, "Failed to acquire lock"
        
        # Try to acquire immediately (should fail)
        lock2 = RedisDistributedLock(redis, "timeout_lock", timeout=2)
        acquired2 = await lock2.acquire(blocking=False)
        assert not acquired2, "Lock should not be available immediately"
        
        # Wait for timeout
        print("⏳ Waiting for lock timeout (2 seconds)...")
        await asyncio.sleep(2.5)
        
        # Now lock should be available due to auto-expiry
        lock3 = RedisDistributedLock(redis, "timeout_lock", timeout=2)
        acquired3 = await lock3.acquire(blocking=False)
        assert acquired3, "Lock should be available after timeout"
        
        await lock3.release()
        
        print("✅ PASS: Lock timeout and auto-release working correctly")
        
    finally:
        await redis.close()

@pytest.mark.asyncio
async def test_lock_prevents_race_condition():
    """
    Test: Lock prevents race condition in counter increment
    Compare with and without lock
    """
    redis = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    num_increments = 500
    
    async def increment_without_lock(counter_key: str):
        """Increment without lock (unsafe)"""
        value = await redis.get(counter_key) or "0"
        new_value = int(value) + 1
        await asyncio.sleep(0.001)  # Simulate processing
        await redis.set(counter_key, str(new_value))
    
    async def increment_with_lock(counter_key: str):
        """Increment with lock (safe)"""
        lock = RedisDistributedLock(redis, f"{counter_key}_lock", timeout=5)
        async with lock:
            value = await redis.get(counter_key) or "0"
            new_value = int(value) + 1
            await asyncio.sleep(0.001)  # Simulate processing
            await redis.set(counter_key, str(new_value))
    
    try:
        # Test WITHOUT lock (expect race conditions)
        await redis.set("counter_unsafe", "0")
        tasks = [increment_without_lock("counter_unsafe") for _ in range(num_increments)]
        await asyncio.gather(*tasks, return_exceptions=True)
        unsafe_value = int(await redis.get("counter_unsafe") or "0")
        
        # Test WITH lock (expect no race conditions)
        await redis.set("counter_safe", "0")
        tasks = [increment_with_lock("counter_safe") for _ in range(num_increments)]
        await asyncio.gather(*tasks, return_exceptions=True)
        safe_value = int(await redis.get("counter_safe") or "0")
        
        print("\n" + "="*60)
        print("🔒 Lock Effectiveness Test")
        print("="*60)
        print(f"Expected Value:            {num_increments}")
        print(f"WITHOUT Lock (unsafe):     {unsafe_value} (lost: {num_increments - unsafe_value})")
        print(f"WITH Lock (safe):          {safe_value} (lost: {num_increments - safe_value})")
        print("="*60)
        
        # Assertions
        assert unsafe_value < num_increments, \
            "⚠️  Expected race condition without lock (this is OK if system is not under load)"
        
        assert safe_value == num_increments, \
            f"❌ Race condition detected even WITH lock! Expected {num_increments}, got {safe_value}"
        
        print("✅ PASS: Lock successfully prevents race conditions")
        print(f"   Prevented {num_increments - unsafe_value} lost updates")
        
    finally:
        await redis.close()

@pytest.mark.asyncio
async def test_multiple_independent_locks():
    """
    Test: Multiple independent locks can be held simultaneously
    Expected: Different locks don't interfere with each other
    """
    redis = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    
    results = {"lock_a": [], "lock_b": [], "lock_c": []}
    
    async def worker(lock_name: str, worker_id: int):
        """Worker for specific lock"""
        lock = RedisDistributedLock(redis, lock_name, timeout=5)
        async with lock:
            results[lock_name].append(worker_id)
            await asyncio.sleep(0.1)
    
    try:
        # Create workers for different locks
        tasks = []
        for i in range(10):
            tasks.append(worker("lock_a", i))
            tasks.append(worker("lock_b", i))
            tasks.append(worker("lock_c", i))
        
        await asyncio.gather(*tasks)
        
        print("\n" + "="*60)
        print("🔐 Multiple Independent Locks Test")
        print("="*60)
        print(f"Lock A acquisitions:   {len(results['lock_a'])}")
        print(f"Lock B acquisitions:   {len(results['lock_b'])}")
        print(f"Lock C acquisitions:   {len(results['lock_c'])}")
        print("="*60)
        
        # Each lock should have been acquired 10 times
        assert len(results['lock_a']) == 10, "Lock A not acquired correctly"
        assert len(results['lock_b']) == 10, "Lock B not acquired correctly"
        assert len(results['lock_c']) == 10, "Lock C not acquired correctly"
        
        print("✅ PASS: Multiple independent locks work correctly")
        
    finally:
        await redis.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])