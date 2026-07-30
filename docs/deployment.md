# Deployment (VPS + Portainer)

## Important

Docker Compose **does not** pull git branches by itself. Auto-update after merge to `main` is done via:

1. [`scripts/deploy.sh`](../scripts/deploy.sh) on the server
2. [GitHub Actions](../.github/workflows/deploy.yml) that SSHs in and runs that script on every push to `main`

## Manual update (SSH)

```bash
cd /opt/leadintel   # or your DEPLOY_PATH
./scripts/deploy.sh
```

Equivalent without the script:

```bash
git pull origin main
docker compose -f infra/docker-compose.yml --env-file infra/.env -p leadintel up -d --build
```

## Portainer

If the stack was created from this compose file:

1. Open **Stacks** → `leadintel` (or your stack name)
2. **Editor** / **Pull and redeploy** is for **image** tags — it will **not** apply local git code changes unless you rebuild
3. Preferred with our setup:
   - SSH (or console) → `./scripts/deploy.sh`
   - Or trigger GitHub Action **Deploy production** → Run workflow
4. In Portainer → **Containers**: confirm `api`, `workers`, `dashboard` restarted; check logs if health fails

To recreate from Portainer after git pull on disk:

- Stacks → stack → **Update the stack** → enable **Re-pull image** / rebuild if your Portainer version supports build contexts  
- If Portainer only tracks pre-built images, keep using `deploy.sh` (it runs `compose up --build`)

## One-time VPS setup for auto-deploy

```bash
git clone <YOUR_REPO_URL> /opt/leadintel
cd /opt/leadintel
cp .env.example infra/.env
# edit infra/.env: secrets, APP_BASE_URL, FEATURE_ODOO_CONNECTOR, FEATURE_FAST_AI, ...
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

GitHub → Settings → Secrets and variables → Actions:

| Secret | Example |
|--------|---------|
| `DEPLOY_HOST` | `5.45.119.172` |
| `DEPLOY_USER` | `root` |
| `DEPLOY_SSH_KEY` | private key contents |
| `DEPLOY_PATH` | `/opt/leadintel` |
| `DEPLOY_PORT` | `22` (optional) |

After that, every merged PR into `main` redeploys automatically.

## Rollback

```bash
cd /opt/leadintel
git log --oneline -5
git checkout <previous_commit>
./scripts/deploy.sh
# later return to main:
git checkout main && ./scripts/deploy.sh
```
