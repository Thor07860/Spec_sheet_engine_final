# Pre-Deployment Checklist

Use this checklist before deploying to Render.

## ✅ Code Quality

- [ ] All tests pass locally
- [ ] No hardcoded secrets in code
- [ ] No `print()` debug statements
- [ ] Error handling in place
- [ ] Logging configured properly
- [ ] Requirements.txt updated
- [ ] No `git` merge conflicts

## ✅ Configuration

- [ ] `.env.example` matches all required variables
- [ ] Local `.env` file created from `.env.example`
- [ ] All secrets loaded from environment variables
- [ ] `DEBUG=false` for production
- [ ] `MIN_CONFIDENCE_SCORE` set appropriately
- [ ] `MIN_TRUST_SCORE` configured
- [ ] Database validation logic in place

## ✅ Database Setup

- [ ] Local database works correctly
- [ ] `create_tables()` runs without errors
- [ ] Schema migrations complete (if any)
- [ ] Trusted sources seeded
- [ ] Equipment templates loaded
- [ ] Backup strategy documented

## ✅ External Services

- [ ] Google Gemini API key valid
  - [ ] Quota: 15 RPM sufficient
  - [ ] Models accessible: gemini-2.5-pro, gemini-2.0-flash
  
- [ ] Serper API key valid
  - [ ] Quota: 100+ searches available
  - [ ] Account active
  
- [ ] AWS S3 credentials valid (if using)
  - [ ] Bucket exists
  - [ ] Endpoint accessible
  - [ ] Permissions correct

## ✅ API Validation

- [ ] `GET /health` works locally
- [ ] `POST /equipment` extracts data correctly
- [ ] Batch endpoints with 2+ items work
- [ ] Error responses formatted correctly
- [ ] Response structure matches PMS contract
- [ ] Specification normalization working
- [ ] No `job_id` in external response ✓
- [ ] `source_document` conditional (omitted if null) ✓

## ✅ Performance

- [ ] Startup time < 5 seconds
- [ ] Single extraction < 30 seconds
- [ ] Batch (6 items) < 2 minutes
- [ ] Redis cache working
- [ ] No memory leaks in local testing

## ✅ Render Preparation

- [ ] GitHub repository created and updated
- [ ] `render.yaml` file present
- [ ] All files committed to git
- [ ] No sensitive files in git history
- [ ] `.watchfilesignore` file present ✓

## ✅ Render Services

- [ ] PostgreSQL connection string obtained
  - [ ] Format: `postgresql://user:pass@host:5432/db`
  - [ ] Database name: `specsheet_engine`
  
- [ ] Redis connection string obtained
  - [ ] Format: `redis://[:password@]host:port`
  - [ ] Instance accessible
  
- [ ] All environment variables prepared
  - [ ] DATABASE_URL
  - [ ] REDIS_URL
  - [ ] GEMINI_API_KEY
  - [ ] SERPER_API_KEY
  - [ ] AWS_* (if using S3)

## ✅ Post-Deployment

- [ ] Health check passes: `/health`
- [ ] API Documentation accessible: `/docs`
- [ ] Sample extraction request succeeds
- [ ] Response format valid JSON
- [ ] Logs show no errors
- [ ] Database connected successfully
- [ ] Redis cache working
- [ ] External APIs responding

## ✅ Monitoring Setup (Optional)

- [ ] Render alerts configured
- [ ] Log review process established
- [ ] Error notification system
- [ ] Performance monitoring dashboard
- [ ] Backup strategy in place

---

## Deployment Steps

### 1. Final Check
```bash
# Run all checks before pushing
python -c "from app.core.config import settings; print('✓ Config loads')"
python -c "from app.core.database import create_tables; print('✓ Tables created')"
curl http://localhost:8000/health
```

### 2. Push to GitHub
```bash
git add .
git commit -m "Deploy: v1.0.0 ready for production"
git push origin main
```

### 3. Deploy on Render
```
Option A: render.yaml (recommended)
- Render auto-detects and deploys all services

Option B: Manual
1. Create PostgreSQL
2. Create Redis
3. Create Web Service
4. Set environment variables
5. Deploy
```

### 4. Verify Deployment
```bash
# Get Render service URL from dashboard
export SERVICE_URL="https://specsheet-engine-api.onrender.com"

# Test health
curl $SERVICE_URL/health

# Test API
curl -X POST $SERVICE_URL/equipment \
  -H "Content-Type: application/json" \
  -d '{
    "manufacturer": "REC",
    "model": "Alpha Pure-R 430W",
    "equipment_type": "module",
    "equipment_sub_type": "pv_module"
  }'
```

### 5. Monitor Logs
```
Render Dashboard → Web Service → Logs
Watch for:
- ✅ "Application startup complete"
- ✅ Successful extraction logs
- ❌ Database connection errors
- ❌ API timeouts
```

---

## Rollback Plan

If something fails after deployment:

1. **Immediate**: Check Render logs for error
2. **Quick fix**: Update environment variable if applicable
3. **Config issue**: Fix and push new commit → auto-redeploy
4. **Critical**: Click "Redeploy" on previous successful commit
5. **Database issue**: Restore from Render backup

---

## Signals of Success

✅ Code is deployed
✅ Services are running
✅ Health check passes
✅ API extracts equipment specs
✅ Response format is PMS-compatible
✅ Logs show no errors
✅ Monitoring is in place

**You're live!** 🚀
