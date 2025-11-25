# Cloudflare DNS Setup Guide

This guide will help you configure Cloudflare as your DNS provider for the GMS Certification Analyzer.

## Benefits of Using Cloudflare

- 🔒 **Free SSL/TLS** - Automatic HTTPS encryption
- 🛡️ **DDoS Protection** - Protection against attacks
- ⚡ **CDN** - Faster content delivery worldwide
- 📊 **Analytics** - Traffic insights and monitoring
- 🔐 **Security Features** - WAF, rate limiting, etc.

## Prerequisites

- A domain name (e.g., `gms-analyzer.yourdomain.com`)
- Cloudflare account (free tier is sufficient)
- Vultr VPS deployed and running

## Setup Steps

### 1. Add Your Domain to Cloudflare

1. Log in to [Cloudflare](https://dash.cloudflare.com/)
2. Click "Add a Site"
3. Enter your domain name (e.g., `yourdomain.com`)
4. Select the **Free** plan
5. Click "Continue"

### 2. Update Nameservers

Cloudflare will provide you with nameservers (e.g., `ns1.cloudflare.com`, `ns2.cloudflare.com`):

1. Go to your domain registrar (GoDaddy, Namecheap, etc.)
2. Find the nameserver settings
3. Replace existing nameservers with Cloudflare's nameservers
4. Save changes (DNS propagation can take up to 24 hours)

### 3. Add DNS Record for Your VPS

In Cloudflare DNS settings:

1. Click "DNS" in the sidebar
2. Click "Add record"
3. Configure:
   - **Type**: `A`
   - **Name**: `gms` (or your preferred subdomain)
   - **IPv4 address**: Your Vultr VPS IP
   - **Proxy status**: ✅ Proxied (orange cloud)
   - **TTL**: Auto
4. Click "Save"

**Example:**
```
Type: A
Name: gms
IPv4: 123.45.67.89
Proxy: Proxied
```

This will make your app accessible at `gms.yourdomain.com`

### 4. Configure SSL/TLS Settings

1. Go to **SSL/TLS** → **Overview**
2. Set encryption mode to **Full** (recommended)
   - **Full**: Encrypts traffic between Cloudflare and your server
   - **Full (strict)**: Requires valid SSL certificate on server (use after setting up Let's Encrypt)

### 5. Update Nginx Configuration on VPS

SSH into your VPS and update the Nginx configuration:

```bash
sudo nano /etc/nginx/sites-available/gms-analyzer
```

Update the `server_name` line:
```nginx
server {
    listen 80;
    server_name gms.yourdomain.com;  # Update this line
    
    # ... rest of configuration
}
```

Test and reload Nginx:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 6. Set Up SSL Certificate (Optional but Recommended)

Even though Cloudflare provides SSL, it's best practice to have SSL on your server too:

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d gms.yourdomain.com

# Follow the prompts
# Choose option 2: Redirect HTTP to HTTPS
```

After this, update Cloudflare SSL mode to **Full (strict)**.

### 7. Configure Cloudflare Security Settings

#### Page Rules (Optional - Free tier allows 3 rules)

1. Go to **Rules** → **Page Rules**
2. Create rule for `gms.yourdomain.com/*`:
   - **Browser Cache TTL**: 4 hours
   - **Security Level**: Medium
   - **Cache Level**: Standard

#### Firewall Rules (Optional)

1. Go to **Security** → **WAF**
2. Enable **OWASP Core Ruleset**
3. Consider adding custom rules:
   - Block countries you don't need
   - Rate limiting for API endpoints

### 8. Optimize Cloudflare Settings

#### Speed Settings
1. Go to **Speed** → **Optimization**
2. Enable:
   - ✅ Auto Minify (JavaScript, CSS, HTML)
   - ✅ Brotli compression
   - ✅ Rocket Loader (test first, may break some JS)

#### Caching
1. Go to **Caching** → **Configuration**
2. Set **Browser Cache TTL**: 4 hours
3. Enable **Always Online**

### 9. Test Your Setup

1. **DNS Propagation**: Check at https://dnschecker.org/
2. **SSL**: Visit `https://gms.yourdomain.com` - should show secure padlock
3. **Application**: Verify all features work correctly

## Cloudflare Configuration for Large File Uploads

Since GMS test results can be large XML files, configure these settings:

### 1. Increase Upload Limits

Cloudflare Free tier has a **100MB upload limit**. For larger files:

**Option A: Use Cloudflare Pro** ($20/month)
- Supports up to 500MB uploads

**Option B: Bypass Cloudflare for Uploads**
1. Create a separate subdomain: `upload.yourdomain.com`
2. Point it directly to your VPS IP (grey cloud, not proxied)
3. Update your app to use this subdomain for uploads

**Option C: Use Cloudflare Workers** (Advanced)
- Implement chunked uploads via Workers
- Free tier allows 100,000 requests/day

### 2. Configure Nginx for Large Uploads

Already configured in `deploy_vultr.sh`, but verify:

```nginx
client_max_body_size 1000M;
proxy_connect_timeout 600;
proxy_send_timeout 600;
proxy_read_timeout 600;
```

## Recommended Cloudflare Settings Summary

| Setting | Value | Location |
|---------|-------|----------|
| SSL/TLS Mode | Full (strict) | SSL/TLS → Overview |
| Always Use HTTPS | ✅ On | SSL/TLS → Edge Certificates |
| Auto Minify | ✅ JS, CSS, HTML | Speed → Optimization |
| Brotli | ✅ On | Speed → Optimization |
| Browser Cache TTL | 4 hours | Caching → Configuration |
| Security Level | Medium | Security → Settings |
| Challenge Passage | 30 minutes | Security → Settings |

## Monitoring and Analytics

### Cloudflare Analytics
1. Go to **Analytics & Logs** → **Traffic**
2. Monitor:
   - Requests per day
   - Bandwidth usage
   - Threats blocked
   - Response time

### Set Up Alerts
1. Go to **Notifications**
2. Enable alerts for:
   - SSL certificate expiration
   - DDoS attacks
   - High error rates

## Troubleshooting

### "Too Many Redirects" Error
**Cause**: SSL/TLS mode mismatch
**Solution**: 
1. Set Cloudflare SSL to "Full" or "Flexible"
2. Or ensure your server has valid SSL certificate

### 502 Bad Gateway
**Cause**: Nginx or application not running
**Solution**:
```bash
sudo supervisorctl status gms-analyzer
sudo systemctl status nginx
```

### Upload Fails for Large Files
**Cause**: Cloudflare 100MB limit
**Solution**: Use one of the options in "Large File Uploads" section above

### Slow Performance
**Cause**: Cloudflare caching not optimized
**Solution**:
1. Check cache hit ratio in Analytics
2. Create page rules for static assets
3. Enable Argo Smart Routing (paid feature)

## Advanced: Cloudflare Tunnel (Alternative to Direct IP)

For enhanced security, use Cloudflare Tunnel instead of exposing your VPS IP:

```bash
# Install cloudflared on VPS
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Authenticate
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create gms-analyzer

# Configure tunnel
cloudflared tunnel route dns gms-analyzer gms.yourdomain.com

# Run tunnel
cloudflared tunnel run gms-analyzer
```

This eliminates the need to expose your VPS IP publicly.

## Cost Considerations

- **Cloudflare Free**: $0/month
  - Sufficient for most use cases
  - 100MB upload limit
  
- **Cloudflare Pro**: $20/month
  - 500MB upload limit
  - Advanced DDoS protection
  - Image optimization

- **Cloudflare Business**: $200/month
  - Custom SSL certificates
  - Advanced security features

For GMS Analyzer, **Free tier is recommended** unless you need larger uploads.

## Next Steps

1. ✅ Set up Cloudflare DNS
2. ✅ Configure SSL/TLS
3. ✅ Update Nginx configuration
4. ✅ Test the deployment
5. 📝 Document your domain for team members
6. 🔐 Configure OpenAI and Redmine settings in the app

Your GMS Certification Analyzer will now be accessible at:
**https://gms.yourdomain.com** 🚀
