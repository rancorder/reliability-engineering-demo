#!/bin/bash

###############################################################################
# Reliability Engineering Demo - Quick Start Script
# Netflix/Google SRE Level Implementation
###############################################################################

set -e  # Exit on error

echo "=================================="
echo "🔬 Reliability Engineering Demo"
echo "=================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo "ℹ️  $1"
}

# Check prerequisites
echo "📋 Checking prerequisites..."
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi
print_success "Docker is installed"

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi
print_success "Docker Compose is installed"

# Check Docker daemon
if ! docker info &> /dev/null; then
    print_error "Docker daemon is not running"
    echo "Please start Docker Desktop or Docker daemon"
    exit 1
fi
print_success "Docker daemon is running"

echo ""
echo "=================================="
echo "🏗️  Building Docker images..."
echo "=================================="
echo ""

# Build images
if docker-compose build; then
    print_success "All images built successfully"
else
    print_error "Failed to build images"
    exit 1
fi

echo ""
echo "=================================="
echo "🚀 Starting services..."
echo "=================================="
echo ""

# Start services
if docker-compose up -d; then
    print_success "All services started"
else
    print_error "Failed to start services"
    exit 1
fi

echo ""
echo "⏳ Waiting for services to be ready (30 seconds)..."
sleep 30

echo ""
echo "=================================="
echo "🏥 Checking service health..."
echo "=================================="
echo ""

# Health check
MAX_RETRIES=10
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/health > /dev/null; then
        print_success "Application is healthy"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT+1))
        if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
            print_error "Application failed to start"
            echo ""
            echo "Check logs with: make logs"
            exit 1
        fi
        print_warning "Waiting for application... (attempt $RETRY_COUNT/$MAX_RETRIES)"
        sleep 5
    fi
done

echo ""
echo "=================================="
echo "✅ Setup Complete!"
echo "=================================="
echo ""

echo "📊 Access Points:"
echo "  • Application:  http://localhost:8000"
echo "  • Health Check: http://localhost:8000/health"
echo "  • Metrics:      http://localhost:8000/metrics"
echo "  • Grafana:      http://localhost:3000 (admin/admin)"
echo "  • Prometheus:   http://localhost:9090"
echo "  • Locust UI:    http://localhost:8089 (when started)"
echo ""

echo "🎯 Next Steps:"
echo ""
echo "  1. Run smoke test:"
echo "     make k6-smoke"
echo ""
echo "  2. View Grafana dashboard:"
echo "     open http://localhost:3000"
echo ""
echo "  3. Run load test:"
echo "     make k6-load"
echo ""
echo "  4. Run concurrency tests:"
echo "     make test-concurrency"
echo ""
echo "  5. Run chaos tests:"
echo "     make chaos-all"
echo ""
echo "  6. See all available commands:"
echo "     make help"
echo ""

echo "=================================="
echo "🔥 Ready to demonstrate Netflix/Google SRE level skills!"
echo "=================================="
echo ""

# Optional: Run smoke test
read -p "Run smoke test now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "=================================="
    echo "🔥 Running Smoke Test..."
    echo "=================================="
    echo ""
    make k6-smoke
    echo ""
    print_success "Smoke test completed!"
    echo ""
    echo "Check results in: k6/results/"
fi

echo ""
echo "Happy testing! 🚀"