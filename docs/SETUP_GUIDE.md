# LogicGate Multi-Tenant SaaS Setup Guide

## Overview

This guide covers setting up the LogicGate multi-tenant SaaS platform for production deployment. This is a commercial SaaS platform that handles customer data, payments, and multi-tenant isolation.

## Required API Keys and Configuration

### 1. Stripe Payment Processing (Required for billing)

**Why needed:** Handles subscription payments, invoicing, and recurring billing.

**How to get:**
1. Create a Stripe account at https://stripe.com
2. Navigate to Dashboard → Developers → API keys
3. Copy your test keys for development:
   - `STRIPE_SECRET_KEY` (starts with `sk_test_`)
   - `STRIPE_PUBLISHABLE_KEY` (starts with `pk_test_`)
4. For production, use live keys (starts with `sk_live_` and `pk_live_`)
5. Set up webhook endpoint for payment events:
   - Dashboard → Developers → Webhooks → Add endpoint
   - Point to: `https://your-domain.com/stripe/webhook`
   - Copy the webhook signing secret: `STRIPE_WEBHOOK_SECRET`

**Cost:** Stripe charges 2.9% + 30¢ per successful transaction.

### 2. JWT Secret Key (Required)

**Why needed:** Secures authentication tokens for user sessions.

**How to generate:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Security:** Keep this secret! Never commit to version control.

### 3. Email Service API Key (Required for notifications)

**Options:**

**SendGrid (Recommended):**
1. Create account at https://sendgrid.com
2. Generate API key: Settings → API Keys → Create API Key
3. Use SMTP relay credentials in `.env`

**AWS SES (Cost-effective for high volume):**
1. Enable SES in AWS Console
2. Verify sending domain/email
3. Create SMTP credentials

**Mailgun:**
1. Create account at https://www.mailgun.com
2. Get API key from dashboard
3. Configure SMTP settings

**Cost:** SendGrid free tier (100 emails/day), paid tiers from $15/month.

### 4. Database Configuration

**Development:** SQLite (included, no configuration needed)

**Production (Recommended):** PostgreSQL or MySQL
- Host: Your database server
- Port: 5432 (PostgreSQL) or 3306 (MySQL)
- Username/Password: Database credentials
- Database name: Separate database per tenant or shared schema

### 5. Redis (Optional but recommended)

**Why needed:** Distributed rate limiting, session management, caching.

**How to set up:**
```bash
# Install Redis
# Windows: Download from https://github.com/microsoftarchive/redis/releases
# Linux: sudo apt-get install redis-server
# macOS: brew install redis
```

**Cost:** Self-hosted (free) or Redis Cloud (from $5/month).

### 6. Cloud Storage (Optional)

**Why needed:** Store tenant logos, file uploads, backups.

**Options:**
- AWS S3
- Google Cloud Storage
- Azure Blob Storage
- MinIO (self-hosted)

## Commercial Liability Considerations

### Legal Requirements

**This is a commercially liable SaaS platform. You should consult with legal professionals about:**

1. **Terms of Service (ToS)**
   - Define service scope and limitations
   - Liability limitations
   - Termination clauses
   - Data ownership and portability

2. **Privacy Policy**
   - Data collection practices
   - Data storage and processing
   - User rights (access, deletion, portability)
   - Third-party data sharing

3. **Data Protection Compliance**
   - **GDPR** (if serving EU customers)
   - **CCPA** (if serving California residents)
   - Industry-specific regulations (healthcare, finance, etc.)

4. **Payment Processing Compliance**
   - Stripe handles most PCI DSS requirements
   - You still need proper data handling practices
   - Never store full card numbers

5. **Liability Insurance**
   - Cyber liability insurance
   - Professional liability insurance
   - General liability insurance

6. **Business Structure**
   - LLC or corporation for liability protection
   - Proper business registration
   - Tax obligations

### Recommended Legal Documents

- Terms of Service
- Privacy Policy
- Data Processing Agreement (DPA)
- Service Level Agreement (SLA)
- Acceptable Use Policy

## Setup Steps

### Step 1: Environment Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your actual values:
```bash
# JWT Secret (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
JWT_SECRET=your_generated_secret_here

# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Email Configuration
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.your_sendgrid_api_key
SMTP_FROM=noreply@yourdomain.com

# Application Configuration
APP_NAME=Your Company Name
APP_URL=https://yourdomain.com
PORTAL_URL=https://yourdomain.com/portal
```

### Step 2: Database Setup

**Development (SQLite):**
```bash
# Database is auto-created on first run
python fix_migration.py  # Run migration script
```

**Production (PostgreSQL):**
```bash
# Install PostgreSQL
# Create database
createdb logicgate_shared

# Update .env
SHARED_DB_TYPE=postgresql
SHARED_DB_HOST=localhost
SHARED_DB_PORT=5432
SHARED_DB_NAME=logicgate_shared
SHARED_DB_USER=logicgate
SHARED_DB_PASSWORD=your_password
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Required packages:**
- `jinja2` - Template rendering
- `stripe` - Payment processing
- `python-dotenv` - Environment configuration
- `redis` - Caching and rate limiting
- `psycopg2-binary` - PostgreSQL (if using PostgreSQL)

### Step 4: Run Migrations

```bash
python fix_migration.py
```

This creates:
- Tenants table
- Tenant branding table
- Subscription plans table
- API keys table
- Usage tracking tables

### Step 5: Configure Stripe Products and Prices

1. Log into Stripe Dashboard
2. Create products for your subscription tiers:
   - Starter Plan
   - Professional Plan
   - Enterprise Plan
3. Create recurring prices for each plan
4. Copy price IDs to your database or configuration

### Step 6: Test the Portal

```bash
# Start the server
python ground_station.py

# Access the portal
http://localhost:8080/portal
```

### Step 7: Set Up Custom Domains (Multi-Tenant)

For each tenant, you can set up:
1. Subdomain: `tenant.yourdomain.com`
2. Custom domain: `tenant.com`

**DNS Configuration:**
```
# Subdomain
tenant.yourdomain.com → A → your_server_ip

# Custom domain
tenant.com → CNAME → tenant.yourdomain.com
```

**SSL Certificates:**
Use Let's Encrypt with Certbot:
```bash
sudo certbot certonly --webroot -w /var/www/html -d tenant.yourdomain.com
```

## Production Deployment Checklist

- [ ] Set up production database (PostgreSQL recommended)
- [ ] Configure Redis for session management
- [ ] Set up SSL certificates (HTTPS required for payments)
- [ ] Configure firewall rules
- [ ] Set up monitoring (Sentry, DataDog, or similar)
- [ ] Configure backups (database and file storage)
- [ ] Set up log aggregation
- [ ] Configure rate limiting
- [ ] Set up CDN for static assets
- [ ] Configure email service
- [ ] Test Stripe webhook endpoints
- [ ] Set up automated deployment pipeline
- [ ] Configure health checks
- [ ] Set up alerting for critical failures
- [ ] Review and update legal documents
- [ ] Obtain liability insurance
- [ ] Set up customer support channels

## Security Best Practices

1. **Never commit `.env` file** to version control
2. **Use strong, unique JWT secrets**
3. **Enable HTTPS only** in production
4. **Implement rate limiting** on all API endpoints
5. **Regular security updates** for all dependencies
6. **Encrypt sensitive data** at rest and in transit
7. **Implement proper authentication** (not the development bypass)
8. **Regular security audits** and penetration testing
9. **Monitor for suspicious activity**
10. **Have incident response plan** ready

## Monitoring and Maintenance

**Key metrics to monitor:**
- Server uptime and response times
- Database query performance
- API error rates
- Payment success rates
- Tenant usage patterns
- Storage utilization
- Security events

**Regular maintenance tasks:**
- Database backups (daily)
- Log rotation
- Security patching
- SSL certificate renewal
- Performance optimization
- Capacity planning

## Support Resources

- Stripe Documentation: https://stripe.com/docs
- SendGrid Documentation: https://docs.sendgrid.com
- PostgreSQL Documentation: https://www.postgresql.org/docs
- Redis Documentation: https://redis.io/documentation

## Legal Disclaimer

This guide provides technical setup instructions only. It does not constitute legal advice. You should consult with qualified legal professionals to ensure compliance with all applicable laws and regulations in your jurisdiction, including but not limited to data protection laws, payment processing regulations, and liability requirements.

## Cost Estimates

**Monthly operating costs (approximate):**
- Hosting: $20-100/month (depending on scale)
- Database: $15-50/month (managed PostgreSQL)
- Email: $15-50/month (SendGrid)
- Storage: $5-20/month (S3 or similar)
- Domain: $10-15/year per domain
- SSL: Free (Let's Encrypt)
- Monitoring: $0-50/month
- **Total: $55-235/month** for small deployment

**Stripe fees:** 2.9% + 30¢ per transaction (paid by customers)

**Insurance:** $500-2000/year (cyber liability)

---

**Next Steps:**
1. Obtain required API keys
2. Configure `.env` file
3. Set up production database
4. Deploy to staging environment
5. Test all functionality
6. Deploy to production
7. Set up monitoring and alerts
8. Launch to customers
