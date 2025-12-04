/**
 * k6 Load Test - Standard Load Testing
 * Target: 100 VUs for 5 minutes
 * Threshold: p95 < 200ms, Error rate < 1%
 */
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom Metrics
const errorRate = new Rate('errors');
const requestDuration = new Trend('request_duration');
const successfulRequests = new Counter('successful_requests');

// Test Configuration
export const options = {
  stages: [
    { duration: '1m', target: 20 },   // Ramp-up to 20 users
    { duration: '3m', target: 100 },  // Ramp-up to 100 users
    { duration: '2m', target: 100 },  // Stay at 100 users
    { duration: '1m', target: 0 },    // Ramp-down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<200', 'p(99)<500'],  // 95% < 200ms, 99% < 500ms
    http_req_failed: ['rate<0.01'],                  // Error rate < 1%
    errors: ['rate<0.01'],
    successful_requests: ['count>10000'],            // At least 10k successful requests
  },
};

const BASE_URL = 'http://app:8000';

// Test scenarios
const scenarios = [
  { name: 'GET /', weight: 30 },
  { name: 'GET /api/fast', weight: 40 },
  { name: 'GET /api/medium', weight: 20 },
  { name: 'GET /api/slow', weight: 10 },
];

export default function () {
  // Select random scenario based on weight
  const rand = Math.random() * 100;
  let cumulative = 0;
  let selectedScenario;

  for (const scenario of scenarios) {
    cumulative += scenario.weight;
    if (rand <= cumulative) {
      selectedScenario = scenario;
      break;
    }
  }

  // Execute request
  const startTime = new Date();
  let response;

  switch (selectedScenario.name) {
    case 'GET /':
      response = http.get(`${BASE_URL}/`);
      break;
    case 'GET /api/fast':
      response = http.get(`${BASE_URL}/api/fast`);
      break;
    case 'GET /api/medium':
      response = http.get(`${BASE_URL}/api/medium`);
      break;
    case 'GET /api/slow':
      response = http.get(`${BASE_URL}/api/slow`);
      break;
  }

  const duration = new Date() - startTime;

  // Validate response
  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
    'has valid body': (r) => r.body && r.body.length > 0,
  });

  // Record metrics
  errorRate.add(!success);
  requestDuration.add(duration);
  if (success) {
    successfulRequests.add(1);
  }

  // Think time (realistic user behavior)
  sleep(Math.random() * 2 + 1); // 1-3 seconds
}

export function handleSummary(data) {
  return {
    '/results/load-test-summary.json': JSON.stringify(data, null, 2),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}

function textSummary(data, options) {
  const indent = options.indent || '';
  const enableColors = options.enableColors || false;

  let summary = '\n';
  summary += `${indent}✅ Load Test Summary\n`;
  summary += `${indent}${'='.repeat(50)}\n\n`;

  // HTTP Metrics
  const httpReqDuration = data.metrics.http_req_duration;
  summary += `${indent}📊 HTTP Request Duration:\n`;
  summary += `${indent}  - Average: ${httpReqDuration.values.avg.toFixed(2)}ms\n`;
  summary += `${indent}  - Median:  ${httpReqDuration.values.med.toFixed(2)}ms\n`;
  summary += `${indent}  - P95:     ${httpReqDuration.values['p(95)'].toFixed(2)}ms\n`;
  summary += `${indent}  - P99:     ${httpReqDuration.values['p(99)'].toFixed(2)}ms\n`;
  summary += `${indent}  - Max:     ${httpReqDuration.values.max.toFixed(2)}ms\n\n`;

  // Request Rate
  const httpReqs = data.metrics.http_reqs;
  summary += `${indent}🔥 Request Rate:\n`;
  summary += `${indent}  - Total:   ${httpReqs.values.count}\n`;
  summary += `${indent}  - Rate:    ${httpReqs.values.rate.toFixed(2)} req/s\n\n`;

  // Error Rate
  const httpReqFailed = data.metrics.http_req_failed;
  summary += `${indent}❌ Error Rate:\n`;
  summary += `${indent}  - Failed:  ${(httpReqFailed.values.rate * 100).toFixed(2)}%\n\n`;

  // Threshold Results
  summary += `${indent}🎯 Threshold Results:\n`;
  for (const [name, threshold] of Object.entries(data.thresholds)) {
    const passed = threshold.ok ? '✅ PASS' : '❌ FAIL';
    summary += `${indent}  - ${name}: ${passed}\n`;
  }

  return summary;
}