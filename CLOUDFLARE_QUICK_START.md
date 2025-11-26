# Quick Start: Cloudflare DNS-Only Mode (No Proxy)

This is the simplest setup for testing - bypasses Cloudflare's 100MB upload limit with zero code changes.

## ✅ Advantages
- **Zero code changes** - App works as-is
- **Unlimited uploads** - No file size restrictions
- **Free SSL** - Use Let's Encrypt on your server
- **Easy to switch** - Can enable proxy later when needed

## ⚠️ Trade-offs
- No Cloudflare DDoS protection (your VPS IP is exposed)
- No CDN caching (slightly slower for global users)
- No Cloudflare WAF (Web Application Firewall)

---

## 🚀 Setup Steps

### 1. Add Your Domain to Cloudflare
1. Go to https://dash.cloudflare.com/
2. Click "Add a Site"
3. Enter your domain: `yourdomain.com`
4. Choose **Free** plan
5. Click "Continue"

### 2. Update Nameservers at Your Registrar
Cloudflare will show you nameservers like:
```
ns1.cloudflare.com
ns2.cloudflare.com
```

Go to your domain registrar (GoDaddy, Namecheap, etc.) and update nameservers.

### 3. Add DNS Record (DNS-Only Mode)

In Cloudflare DNS settings:

1. Click **DNS** → **Records**
2. Click **Add record**
3. Configure:
   - **Type**: `A`
   - **Name**: `gms` (or `@` for root domain)
   - **IPv4 address**: Your Vultr VPS IP
   - **Proxy status**: ⚪ **DNS only** (grey cloud) ← **IMPORTANT!**
   - **TTL**: Auto
4. Click **Save**

**Visual Guide:**
```
┌─────────────────────────────────────────┐
│ Type: A                                 │
│ Name: gms                               │
│ IPv4: 123.45.67.89                      │
│ Proxy: ⚪ DNS only  (NOT 🟠 Proxied)   │
│ TTL: Auto                               │
└─────────────────────────────────────────┘
```

### 4. Configure SSL on Your VPS

SSH into your VPS and set up Let's Encrypt:

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d gms.yourdomain.com

# Follow prompts:
# - Enter your email
# - Agree to terms
# - Choose option 2: Redirect HTTP to HTTPS
```

### 5. Update Nginx Configuration

Edit Nginx config:
```bash
sudo nano /etc/nginx/sites-available/gms-analyzer
```

Update the `server_name`:
```nginx
server {
    listen 80;
    server_name gms.yourdomain.com;  # ← Update this
    
    # ... rest stays the same
}
```

Test and reload:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 6. Test Your Setup

1. **Wait for DNS propagation** (5-30 minutes)
   - Check at: https://dnschecker.org/

2. **Access your app**:
   ```
   https://gms.yourdomain.com
   ```

3. **Test file upload**:
   - Upload a large test XML file (>100MB)
   - Should work without any limits!

---

## 🔄 Later: Enable Cloudflare Proxy (Optional)

If you want to add Cloudflare protection later, you'll need to:

### Option A: Keep DNS-Only (Recommended for now)
- Just leave it as-is
- Unlimited uploads, simple setup

### Option B: Enable Proxy + Separate Upload Subdomain
When you're ready for production:

1. **Create upload subdomain**:
   - Add DNS record: `upload.yourdomain.com` (DNS only)
   
2. **Update app code** (1 line):
   ```javascript
   // In app.js, line 329:
   const response = await fetch(`https://upload.yourdomain.com/api/upload`, {
   ```

3. **Enable proxy for main domain**:
   - Change `gms.yourdomain.com` to Proxied (orange cloud)

---

## 📊 Comparison: DNS-Only vs Proxied

| Feature | DNS-Only (Current) | Proxied (Future) |
|---------|-------------------|------------------|
| Upload Limit | ✅ Unlimited | ❌ 100MB |
| DDoS Protection | ❌ No | ✅ Yes |
| CDN Caching | ❌ No | ✅ Yes |
| SSL | ✅ Let's Encrypt | ✅ Cloudflare |
| Code Changes | ✅ None | ⚠️ 1 line (with upload subdomain) |
| Cost | ✅ Free | ✅ Free |

---

## 🔒 Security Recommendations (DNS-Only Mode)

Since you're not using Cloudflare's proxy, secure your VPS:

### 1. Enable UFW Firewall
```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw --force enable
```

### 2. Install Fail2Ban (Prevent Brute Force)
```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 3. Keep System Updated
```bash
sudo apt update && sudo apt upgrade -y
```

### 4. Use Strong Passwords
- Change default SSH password
- Consider SSH key-only authentication

---

## 🆘 Troubleshooting

### DNS Not Resolving
**Problem**: Can't access `gms.yourdomain.com`

**Solution**:
1. Check DNS propagation: https://dnschecker.org/
2. Wait 5-30 minutes for DNS to propagate
3. Clear your browser cache: `Ctrl+Shift+Del`

### SSL Certificate Error
**Problem**: "Your connection is not private"

**Solution**:
```bash
# Re-run Certbot
sudo certbot --nginx -d gms.yourdomain.com --force-renewal
```

### Upload Still Fails
**Problem**: Large files fail to upload

**Solution**:
1. Check Nginx config has `client_max_body_size 1000M;`
2. Restart Nginx: `sudo systemctl restart nginx`
3. Check server logs: `sudo tail -f /var/log/nginx/error.log`

---

## ✅ Quick Checklist

- [ ] Domain added to Cloudflare
- [ ] Nameservers updated at registrar
- [ ] DNS record created (DNS-only, grey cloud)
- [ ] VPS deployed with `deploy_vultr.sh`
- [ ] SSL certificate installed with Certbot
- [ ] Nginx configured with domain name
- [ ] Can access `https://gms.yourdomain.com`
- [ ] File upload tested successfully

---

## 📝 Summary

**For quick testing and unlimited uploads:**
1. Use Cloudflare in **DNS-only mode** (grey cloud)
2. Set up SSL with Let's Encrypt on your VPS
3. No code changes needed
4. Works perfectly for your use case

**When you need more protection:**
- Switch to proxied mode + separate upload subdomain
- Requires 1 line code change
- Adds DDoS protection and CDN

You're all set! 🎉
