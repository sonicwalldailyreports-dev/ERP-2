# Ubuntu production deployment

This deployment runs the API, durable background worker, PostgreSQL, Redis and
the built frontend with Docker Compose. Docker Engine 24+ and the Compose v2
plugin are required.

## First install

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
git clone <repository-url> /opt/small-office
cd /opt/small-office
cp .env.example .env
chmod 600 .env
```

Edit `.env` and set unique random values (for example,
`openssl rand -hex 32` for both `POSTGRES_PASSWORD` and `SECRET_KEY`; the
database password must be URL-safe because it is part of `DATABASE_URL`).
Set the public origin in `CORS_ORIGINS` and configure DNS/TLS at the host
reverse proxy or load balancer. `.env` is intentionally ignored and must never
be committed.

## Deploy and verify

```bash
docker compose pull
docker compose build --pull
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:8080/api/v1/health
docker compose logs --tail=100 backend worker
```

`migrate` runs `alembic upgrade head` before the API and worker start. A failed
migration prevents those services from starting. The frontend listens on
`HTTP_PORT` (8080 by default); expose it through HTTPS only.

## HTTPS and host Nginx

Keep Docker bound to localhost and terminate TLS in a host-level Nginx
installation. Create `/etc/nginx/sites-available/small-office`:

```nginx
server {
    listen 80;
    server_name erp.example.com;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable it, validate Nginx, and issue a certificate:

```bash
sudo ln -s /etc/nginx/sites-available/small-office /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d erp.example.com
```

Set `CORS_ORIGINS` to the resulting HTTPS origin and verify automatic renewal
with `sudo certbot renew --dry-run`.

## Operations

```bash
# Follow service logs (Docker rotates each service's JSON logs).
docker compose logs -f --tail=200 backend worker
# Restart one service, or stop everything without deleting data.
docker compose restart backend
docker compose down
# Upgrade a release.
git fetch --tags
git checkout <release-tag>
docker compose build --pull
docker compose up -d
```

Never use `docker compose down -v` in production: it deletes the database and
Redis volumes. Restart policies recover services after host or process failure.

## PostgreSQL backup and restore

Keep encrypted dumps on separate storage with access restricted to the
operator. Test restores regularly.

```bash
mkdir -p /var/backups/small-office
docker compose exec -T postgres sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > /var/backups/small-office/$(date +%Y%m%d-%H%M).dump
```

For a restore, stop writers, create a separate database (or use a maintenance
window), and restore with the credentials from `.env`:

```bash
docker compose stop backend worker
cat backup.dump | docker compose exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists'
docker compose up -d
```

## Rollback

Keep the previous image/tag and database dump. Stop the API and worker, restore
the dump if the release changed the schema incompatibly, check out the previous
tag, rebuild, and run `docker compose up -d`. Do not run `alembic downgrade`
blindly: review the migration and take a fresh backup first. Verify `/health`,
`/readiness`, and application logs before reopening traffic.

## Security checklist

* Restrict firewall access to SSH and the HTTPS reverse proxy; Compose does not
  publish PostgreSQL or Redis ports.
* Use a secrets manager or protected `.env` file, rotate credentials, and
  enforce encrypted off-host backups.
* Keep base images and the host patched; review `docker compose config` before
  deployment to ensure no secret is printed or committed.
