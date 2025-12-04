"""
Locust Load Testing - Comprehensive User Behavior Simulation
Target: Realistic user patterns with weighted scenarios
"""
from locust import HttpUser, task, between, events
import random
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global statistics
stats = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "redis_ops": 0,
    "db_ops": 0,
}

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Test start event"""
    logger.info("🚀 Starting Locust Load Test")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Test stop event - print final statistics"""
    logger.info("🏁 Locust Load Test Completed")
    logger.info(f"📊 Statistics: {json.dumps(stats, indent=2)}")

class ReliabilityTestUser(HttpUser):
    """
    Simulates realistic user behavior
    Multiple task types with different weights
    """
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Initialize user session"""
        self.user_id = f"user_{random.randint(1000, 9999)}"
        logger.info(f"👤 User {self.user_id} started session")
    
    @task(30)
    def browse_homepage(self):
        """Browse homepage (30% of traffic)"""
        with self.client.get("/", catch_response=True) as response:
            stats["total_requests"] += 1
            if response.status_code == 200:
                stats["successful_requests"] += 1
                response.success()
            else:
                stats["failed_requests"] += 1
                response.failure(f"Got {response.status_code}")
    
    @task(25)
    def fast_api_request(self):
        """Fast API endpoint (25% of traffic)"""
        with self.client.get("/api/fast", catch_response=True) as response:
            stats["total_requests"] += 1
            if response.status_code == 200:
                stats["successful_requests"] += 1
                response.success()
            else:
                stats["failed_requests"] += 1
                response.failure(f"Got {response.status_code}")
    
    @task(20)
    def medium_api_request(self):
        """Medium API endpoint (20% of traffic)"""
        with self.client.get("/api/medium", catch_response=True) as response:
            stats["total_requests"] += 1
            if response.status_code == 200:
                stats["successful_requests"] += 1
                response.success()
            else:
                stats["failed_requests"] += 1
                response.failure(f"Got {response.status_code}")
    
    @task(10)
    def slow_api_request(self):
        """Slow API endpoint (10% of traffic)"""
        with self.client.get("/api/slow", catch_response=True) as response:
            stats["total_requests"] += 1
            if response.status_code == 200:
                stats["successful_requests"] += 1
                response.success()
            else:
                stats["failed_requests"] += 1
                response.failure(f"Got {response.status_code}")
    
    @task(10)
    def redis_operations(self):
        """Redis SET/GET operations (10% of traffic)"""
        key = f"test_key_{random.randint(1, 1000)}"
        value = f"test_value_{random.randint(1, 10000)}"
        
        # SET operation
        with self.client.post(
            f"/api/redis/{key}",
            params={"value": value},
            catch_response=True
        ) as response:
            stats["total_requests"] += 1
            stats["redis_ops"] += 1
            if response.status_code == 200:
                stats["successful_requests"] += 1
                response.success()
            else:
                stats["failed_requests"] += 1
                response.failure(f"Redis SET failed: {response.status_code}")
        
        # GET operation
        with self.client.get(f"/api/redis/{key}", catch_response=True) as response:
            stats["total_requests"] += 1
            stats["redis_ops"] += 1
            if response.status_code == 200:
                stats["successful_requests"] += 1
                response.success()
            else:
                # 404 is acceptable (key might have expired)
                if response.status_code == 404:
                    response.success()
                else:
                    stats["failed_requests"] += 1
                    response.failure(f"Redis GET failed: {response.status_code}")
    
    @task(5)
    def database_operations(self):
        """Database operations (5% of traffic)"""
        with self.client.get("/api/db/reservations", catch_response=True) as response:
            stats["total_requests"] += 1
            stats["db_ops"] += 1
            if response.status_code == 200:
                stats["successful_requests"] += 1
                response.success()
            else:
                stats["failed_requests"] += 1
                response.failure(f"DB query failed: {response.status_code}")

class HeavyUser(HttpUser):
    """
    Heavy user - generates more load
    Used for stress testing specific scenarios
    """
    wait_time = between(0.5, 1.5)
    weight = 1  # Only 10% of users are heavy users
    
    @task
    def heavy_load(self):
        """Batch requests"""
        endpoints = ["/api/fast", "/api/medium", "/"]
        for endpoint in endpoints:
            self.client.get(endpoint)

class ChaosUser(HttpUser):
    """
    Chaos user - occasionally triggers error scenarios
    Used to test error handling
    """
    wait_time = between(5, 10)
    weight = 1  # Rare chaos events
    
    @task
    def trigger_error(self):
        """Trigger intentional error"""
        self.client.get("/api/chaos/error", name="/api/chaos/error (expected failure)")
    
    @task
    def health_check(self):
        """Health check"""
        self.client.get("/health")