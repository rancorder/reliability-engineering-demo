/**
 * k6 Smoke Test - Minimal Verification
 * Target: 10 VUs for 2 minutes
 * Purpose: Verify basic functionality before heavy testing
 */
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom Metrics
const errorRate = new Rate('errors');
const requestDuration = new Trend('request_duration');

// Test Configuration
export const options = {
  stages: [
    { duration: '30s', target: 5 },   // Ramp-up to 5 users
    { duration: '1m', target: 10 },   // Stay at 10 users
    { duration: '30s', target: 0 },   // Ramp-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<100'],  // 95% of requests < 100ms
    http_req_failed: ['rate<0.01'],    // Error rate < 1%
    errors: ['rate<0.01'],
  },
};

const BASE_URL = 'http://app:8000';

export default function () {
  // Test 1: Root endpoint
  let response = http.get(`${BASE_URL}/`);
  let success = check(response, {
    'root status is 200': (r) => r.status === 200,
    'root has body': (r) => r.body && r.body.length > 0,
  });
  errorRate.add(!success);
  requestDuration.add(response.timings.duration);

  sleep(1);

  // Test 2: Health check
  response = http.get(`${BASE_URL}/health`);
  success = check(response, {
    'health status is 200': (r) => r.status === 200,
    'health shows healthy': (r) => r.json('status') === 'healthy',
  });
  errorRate.add(!success);
  requestDuration.add(response.timings.duration);

  sleep(1);

  // Test 3: Fast API endpoint
  response = http.get(`${BASE_URL}/api/fast`);
  success = check(response, {
    'fast api status is 200': (r) => r.status === 200,
    'fast api response time < 50ms': (r) => r.timings.duration < 50,
  });
  errorRate.add(!success);
  requestDuration.add(response.timings.duration);

  sleep(2);
}

export function handleSummary(data) {
  console.log('\n' + '='.repeat(60));
  console.log('🔥 Smoke Test Summary');
  console.log('='.repeat(60));
  
  const httpReqDuration = data.metrics.http_req_duration;
  console.log('\n📊 Performance:');
  console.log(`  Average: ${httpReqDuration.values.avg.toFixed(2)}ms`);
  console.log(`  P95:     ${httpReqDuration.values['p(95)'].toFixed(2)}ms`);
  
  const httpReqs = data.metrics.http_reqs;
  console.log('\n🔥 Requests:');
  console.log(`  Total:   ${httpReqs.values.count}`);
  console.log(`  Rate:    ${httpReqs.values.rate.toFixed(2)} req/s`);
  
  const httpReqFailed = data.metrics.http_req_failed;
  console.log('\n❌ Errors:');
  console.log(`  Failed:  ${(httpReqFailed.values.rate * 100).toFixed(2)}%`);
  
  // Check if all thresholds passed
  let allPassed = true;
  console.log('\n🎯 Thresholds:');
  for (const [name, threshold] of Object.entries(data.thresholds)) {
    const status = threshold.ok ? '✅ PASS' : '❌ FAIL';
    console.log(`  ${name}: ${status}`);
    if (!threshold.ok) allPassed = false;
  }
  
  console.log('\n' + '='.repeat(60));
  if (allPassed) {
    console.log('✅ Smoke test PASSED - Ready for load testing!');
  } else {
    console.log('❌ Smoke test FAILED - Fix issues before load testing!');
  }
  console.log('='.repeat(60) + '\n');
  
  return {
    '/results/smoke-test-summary.json': JSON.stringify(data, null, 2),
  };
}