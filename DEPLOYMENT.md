# Deployment Guide - Solar Equipment Intelligence Engine

## Table of Contents
1. [Development Setup](#development-setup)
2. [Render Deployment](#render-deployment)
3. [Environment Variables](#environment-variables)
4. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
5. [Scaling](#scaling)

---

## Development Setup

### Prerequisites
- Python 3.11+
- Git
- PostgreSQL (local or managed)
- Redis (local or managed)

### Installation

```bash
# Clone repository
git clone <repo-url> specsheet-engine
cd specsheet-engine

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your local values
nano .env  # or use your editor

# Run migrations (if any)
python -c "from app.core.database import create_tables; create_tables()"

# Start development server
uvicorn app.main:app --reload --reload-dir app
```

Server runs on: http://localhost:8000

API Docs: http://localhost:8000/docs

---

## Render Deployment

### Quick Start (render.yaml)

This is the **recommended** approach as it automatically creates all services.

```bash
# 1. Push code to GitHub
git add .
git commit -m "Deploy to Render"
git push origin main

# 2. Go to https://render.com/dashboard
# 3. Click "New +" → "Blueprint"
# 4. Connect GitHub repo
# 5. Ensure render.yaml is detected
# 6. Click "Deploy"

# Render will automatically:
# ✅ Create PostgreSQL database
# ✅ Create Redis cache
# ✅ Create FastAPI Web Service
# ✅ Set up environment variables
# ✅ Run pre-deployment checks
```

### Manual Setup (if not using render.yaml)

#### Step 1: Create PostgreSQL Database

```
1. Render Dashboard → PostgreSQL
2. Create new PostgreSQL instance
3. Plan: Standard ($7/month) minimum
4. Database name: specsheet_engine
5. Copy connection string → DATABASE_URL
```

#### Step 2: Create Redis Cache

```
1. Render Dashboard → Redis
2. Create new Redis instance
3. Plan: Starter ($7/month) minimum
4. Copy connection string → REDIS_URL
```

#### Step 3: Create Web Service

```
1. Render Dashboard → Web Services
2. Connect GitHub repository
3. Configure:
   - Name: specsheet-engine-api
   - Runtime: Python 3.11
   - Root Directory: / (or your root)
   - Build Command: pip install -r requirements.txt
   - Start Command:
     gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT}
   - Plan: Standard ($7-12/month base)
```

#### Step 4: Set Environment Variables

In Render Dashboard → Environment:

```
DEBUG=false
APP_NAME=Solar Equipment Intelligence Engine
APP_VERSION=1.0.0

# Required
DATABASE_URL=postgresql://...  (from Step 1)
REDIS_URL=redis://...           (from Step 2)
GEMINI_API_KEY=your_key         (from Google AI Studio)
SERPER_API_KEY=your_key         (from Serper.dev)

# S3 Storage
AWS_ACCESS_KEY_ID=your_id
AWS_SECRET_ACCESS_KEY=your_key
AWS_S3_ENDPOINT=your_endpoint
AWS_S3_BUCKET=your_bucket

# Optional
ENABLE_SERPER_SOURCE_SEARCH=true
ENABLE_GROUNDED_WEB_FALLBACK=true
```

#### Step 5: Deploy

```
Click "Deploy" button. Monitor logs.
```

---

## Environment Variables

### Required Variables

| Variable | Source | Example |
|----------|--------|---------|
| `DATABASE_URL` | Render PostgreSQL | `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | Render Redis | `redis://:pass@host:6379` |
| `GEMINI_API_KEY` | Google AI Studio | `AIzaSy...` |
| `SERPER_API_KEY` | Serper.dev | `serper_...` |

### AWS S3 (Optional)

If using S3 for caching PDFs:

```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_S3_ENDPOINT=your_endpoint
AWS_S3_BUCKET=your_bucket
```

### Configuration Variables

```
DEBUG=false                          # Turn off debug mode in production
MIN_CONFIDENCE_SCORE=0.60           # Minimum extraction confidence
MIN_TRUST_SCORE=50                  # Minimum source trust rating
TARGET_COUNTRY=US                   # Country for search results
```

---

## Monitoring & Troubleshooting

### Check Service Health

```bash
# Local
curl http://localhost:8000/health

# Render
curl https://specsheet-engine-api.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

### View Logs

**Render Dashboard:**
1. Go to your Web Service
2. Click "Logs" tab
3. Filter by service (database, redis, api)

**Local:**
```bash
# Watch logs live
tail -f logs/app.log

# With timestamps
tail -20f logs/app.log
```

### Common Issues

#### ❌ Database Connection Error

```
Error: could not translate host name to address
```

**Fix:** Verify DATABASE_URL is correct in Render environment

#### ❌ Redis Connection Error

```
Error: redis connection timeout
```

**Fix:** 
- Check REDIS_URL in environment
- Wait 2-3 minutes for instance to spin up
- Ensure Redis IP allowlist is open

#### ❌ API Startup Fails

```
Error: psychopg2 not found
```

**Fix:** Rebuild with `pip install -r requirements.txt`

#### ❌ Blank Response / 502 Bad Gateway

```
Reason: timeout waiting for worker
```

**Fix:**
- Increase worker count: `--workers 8`
- Check for long-running requests in logs
- Increase timeout: `--timeout 120`

---

## Scaling

### Horizontal Scaling (Web Workers)

In Render → Web Service → Start Command:

```bash
# Increase workers for more concurrency
gunicorn app.main:app --workers 8 --worker-class uvicorn.workers.UvicornWorker

# Or auto-scale based on CPU
--workers auto  # Uses 2 * CPU_count
```

### Database Scaling

1. Render → PostgreSQL
2. Click settings
3. Upgrade to larger plan
4. Rebuild web service (no downtime)

### Memory Issues

If getting 502 errors:

1. Check Render logs for OOM kills
2. Reduce workers: `--workers 2`
3. Upgrade plan: Standard → Standard Plus
4. Enable connection pooling in DATABASE_URL

---

## Rollback

If deployment fails or causes issues:

**Render:**
1. Go to Web Service → Deploys
2. Find last working deploy
3. Click "Redeploy"

**Local:**
```bash
git revert <commit-hash>
git push origin main
# Render auto-redeploys
```

---

## Performance Tips

### Caching
- Redis TTL: 24 hours (configurable)
- Database query caching: enabled by default
- Browser caching: setup CORS headers if needed

### API Optimization
- Batch requests use 15 parallel workers
- Single requests use extraction pipeline
- Specification normalization reduces payload size

### Monitoring
- Watch API response times in logs
- Monitor database connections
- Track Redis memory usage
- Set up alerts for errors (optional)

---

## Backup & Recovery

### Database Backups

**Render** (automatic):
- Backups run daily
- Retention: 7 days free
- Access in Render dashboard → PostgreSQL

**Manual backup:**
```bash
pg_dump "$DATABASE_URL" > backup.sql
```

### Redis Persistence

Render Redis includes periodic snapshots. For critical data, save to database instead of Redis only.

---

## Support & Documentation

- **Render Docs**: https://render.com/docs
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **Gunicorn Config**: https://docs.gunicorn.org/en/stable/
- **PostgreSQL**: https://www.postgresql.org/docs
- **Redis**: https://redis.io/documentation
