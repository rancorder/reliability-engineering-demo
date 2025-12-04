/**
 * k6 Spike Test - Sudden Traffic Surge
 * Target: Instant spike to 1000 VUs
 * Purpose: Test system resilience under sudden load
 */
import http from 'k6/http';
import { check } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '30s', target: 50 },    // Normal load
    { duration: '10s', target: 1000 },  // SPIKE!
    { duration: '1m', target: 1000 },   // Hold spike
    { duration: '30s', target: 50 },    // Recovery
    { duration: '30s', target: 0 },     // Ramp-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<1000'],  // More lenient during spike
    http_req_failed: ['rate<0.10'],     // Allow 10% error during spike
  },
};

const BASE_URL = 'http://app:8000';

export default function () {
  const response = http.get(`${BASE_URL}/api/fast`);
  
  const success = check(response, {
    'status is 200': (r) => r.status === 200,
  });
  
  errorRate.add(!success);
}