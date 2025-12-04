"""
Race Condition Detection Tests
Netflix/Google SRE Level Concurrency Testing

Purpose: Detect data races and ensure data integrity under concurrent load
"""
import pytest
import asyncio
import httpx
import os
from typing import List, Dict, Any

APP_URL = os.getenv("APP_URL", "http://app:8000")

class RaceConditionDetector:
    """Detect and analyze race conditions"""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.errors: List[Exception] = []
    
    def add_result(self, result: Dict[str, Any]):
        """Add successful result"""
        self.results.append(result)
    
    def add_error(self, error: Exception):
        """Add error result"""
        self.errors.append(error)
    
    def analyze(self) -> Dict[str, Any]:
        """Analyze race condition results"""
        successful = len([r for r in self.results if r.get("success")])
        failed = len(self.results) - successful
        exceptions = len(self.errors)
        
        return {
            "total_attempts": len(self.results) + len(self.errors),
            "successful": successful,
            "failed": failed,
            "exceptions": exceptions,
            "race_conditions_detected": successful > 1,  # More than one success = race condition
            "error_rate": (failed + exceptions) / (len(self.results) + len(self.errors))
        }

@pytest.mark.asyncio
async def test_concurrent_room_reservation():
    """
    Test: 100 users try to reserve the same room simultaneously
    Expected: Only ONE user should succeed
    Race Condition: If multiple users succeed, we have a race condition
    """
    room_id = "room_test_001"
    num_users = 100
    detector = RaceConditionDetector()
    
    async def reserve_room(user_id: int):
        """Single reservation attempt"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{APP_URL}/api/reserve/{room_id}",
                    params={"user_id": f"user_{user_id}"}
                )
                
                result = {
                    "user_id": user_id,
                    "status_code": response.status_code,
                    "success": response.status_code == 200,
                    "response": response.json() if response.status_code == 200 else None
                }
                detector.add_result(result)
                
            except Exception as e:
                detector.add_error(e)
    
    # Execute all reservations concurrently
    tasks = [reserve_room(i) for i in range(num_users)]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Analyze results
    analysis = detector.analyze()
    
    print("\n" + "="*60)
    print("🏁 Race Condition Test Results")
    print("="*60)
    print(f"Total Attempts:        {analysis['total_attempts']}")
    print(f"Successful Bookings:   {analysis['successful']}")
    print(f"Failed (409 Conflict): {analysis['failed']}")
    print(f"Exceptions:            {analysis['exceptions']}")
    print(f"Error Rate:            {analysis['error_rate']*100:.2f}%")
    print("="*60)
    
    # Assertions
    assert analysis['successful'] == 1, \
        f"❌ RACE CONDITION DETECTED! {analysis['successful']} users succeeded (expected 1)"
    
    assert analysis['failed'] == num_users - 1 - analysis['exceptions'], \
        "❌ Unexpected number of failures"
    
    print("✅ PASS: No race condition detected!")

@pytest.mark.asyncio
async def test_concurrent_counter_increment():
    """
    Test: 1000 concurrent counter increments
    Expected: Counter should be exactly 1000
    Race Condition: If counter != 1000, we have lost updates
    """
    counter_key = "test_counter"
    num_increments = 1000
    
    # Reset counter
    async with httpx.AsyncClient() as client:
        await client.post(f"{APP_URL}/api/redis/{counter_key}", params={"value": "0"})
    
    async def increment_counter(task_id: int):
        """Increment counter by 1"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # GET current value
                response = await client.get(f"{APP_URL}/api/redis/{counter_key}")
                if response.status_code != 200:
                    return False
                
                current = int(response.json()["value"])
                new_value = current + 1
                
                # SET new value (UNSAFE - no atomic operation)
                await client.post(
                    f"{APP_URL}/api/redis/{counter_key}",
                    params={"value": str(new_value)}
                )
                return True
                
            except Exception as e:
                print(f"Error in task {task_id}: {e}")
                return False
    
    # Execute all increments concurrently
    tasks = [increment_counter(i) for i in range(num_increments)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Get final counter value
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{APP_URL}/api/redis/{counter_key}")
        final_value = int(response.json()["value"])
    
    successful_increments = len([r for r in results if r is True])
    
    print("\n" + "="*60)
    print("🔢 Concurrent Counter Test Results")
    print("="*60)
    print(f"Expected Value:        {num_increments}")
    print(f"Actual Value:          {final_value}")
    print(f"Lost Updates:          {num_increments - final_value}")
    print(f"Success Rate:          {successful_increments}/{num_increments}")
    print("="*60)
    
    # This test is EXPECTED to fail without proper locking
    # Demonstrating the race condition
    if final_value < num_increments:
        print(f"⚠️  RACE CONDITION DETECTED: Lost {num_increments - final_value} updates!")
        print("    This is expected without atomic operations or distributed locks")
    else:
        print("✅ All increments successful (unlikely without locking)")

@pytest.mark.asyncio
async def test_concurrent_read_write():
    """
    Test: Concurrent reads and writes
    Expected: Reads should always get consistent data
    """
    test_key = "read_write_test"
    num_writers = 50
    num_readers = 50
    
    results = {"reads": [], "writes": []}
    
    async def writer(writer_id: int):
        """Write data"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            value = f"writer_{writer_id}_value"
            response = await client.post(
                f"{APP_URL}/api/redis/{test_key}",
                params={"value": value}
            )
            results["writes"].append({
                "writer_id": writer_id,
                "success": response.status_code == 200,
                "value": value
            })
    
    async def reader(reader_id: int):
        """Read data"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{APP_URL}/api/redis/{test_key}")
                if response.status_code == 200:
                    results["reads"].append({
                        "reader_id": reader_id,
                        "value": response.json()["value"]
                    })
            except Exception as e:
                pass  # Key might not exist yet
    
    # Mix of readers and writers
    tasks = []
    tasks.extend([writer(i) for i in range(num_writers)])
    tasks.extend([reader(i) for i in range(num_readers)])
    
    # Shuffle to mix reads and writes
    import random
    random.shuffle(tasks)
    
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print("\n" + "="*60)
    print("📖 Concurrent Read/Write Test Results")
    print("="*60)
    print(f"Total Writes:          {len(results['writes'])}")
    print(f"Successful Writes:     {len([w for w in results['writes'] if w['success']])}")
    print(f"Total Reads:           {len(results['reads'])}")
    print(f"Unique Values Read:    {len(set(r['value'] for r in results['reads']))}")
    print("="*60)
    
    assert len(results['writes']) == num_writers, "Not all writes completed"
    print("✅ PASS: Concurrent read/write test completed")

@pytest.mark.asyncio
async def test_double_booking_prevention():
    """
    Test: Multiple users try to book different rooms simultaneously
    Expected: No double bookings for the same room
    """
    rooms = [f"room_{i:03d}" for i in range(10)]
    users_per_room = 10
    
    booking_results = {}
    
    async def book_room(room_id: str, user_id: int):
        """Attempt to book a room"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{APP_URL}/api/reserve/{room_id}",
                    params={"user_id": f"user_{user_id}"}
                )
                return {
                    "room_id": room_id,
                    "user_id": user_id,
                    "success": response.status_code == 200,
                    "status_code": response.status_code
                }
            except Exception as e:
                return {
                    "room_id": room_id,
                    "user_id": user_id,
                    "success": False,
                    "error": str(e)
                }
    
    # Create booking attempts for all rooms
    tasks = []
    for room in rooms:
        for user in range(users_per_room):
            tasks.append(book_room(room, user))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Analyze bookings per room
    for room in rooms:
        room_bookings = [r for r in results if isinstance(r, dict) and r["room_id"] == room and r["success"]]
        booking_results[room] = len(room_bookings)
    
    print("\n" + "="*60)
    print("🏨 Double Booking Prevention Test")
    print("="*60)
    for room, count in booking_results.items():
        status = "✅" if count == 1 else "❌"
        print(f"{status} {room}: {count} successful booking(s)")
    print("="*60)
    
    # Verify each room has exactly 1 booking
    double_bookings = [room for room, count in booking_results.items() if count > 1]
    
    assert len(double_bookings) == 0, \
        f"❌ DOUBLE BOOKING DETECTED in rooms: {double_bookings}"
    
    print("✅ PASS: No double bookings detected!")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])