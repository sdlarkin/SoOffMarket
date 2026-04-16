# Git-Ops Deployment SOP (Vercel + DigitalOcean)

This directive defines the automated "Push-to-Deploy" strategy for DanesAppStudio projects, replicating the successful flow from the Central Coast Comedy Theater project.

## 🚀 The Git-Ops Flow

All deployments are triggered by a `git push` to the project's remote repository.

### 1. Frontend (The Build Plane)
- **Target**: Vercel.
- **Trigger**: Push to `main` branch.
- **Mechanism**: Vercel's native GitHub Integration.
- **Workflow**:
  - Connect the client's GitHub repo to a Vercel Project.
  - Vercel automatically detects the Next.js project.
  - Vercel manages SSL and Global CDN.
  - On every push, a production build is triggered.

### 2. Backend (The Control Plane)
- **Target**: DigitalOcean Droplet (Ubuntu + Docker).
- **Trigger**: GitHub Actions (`.github/workflows/deploy.yml`).
- **Mechanism**: `appleboy/ssh-action` for remote execution.
- **Workflow**:
  1. GitHub Action triggers on push to `main`.
  2. Action logs into the DO Droplet via SSH.
  3. Action executes a `git pull` from the remote repository.
  4. Action restarts the application (e.g., `docker-compose up --build -d` or `systemctl restart gunicorn`).

## 🛠️ Required Workflow Template

Each client repository MUST include a `.github/workflows/deploy.yml` file. Here is the standard template:

```yaml
name: Deploy to DigitalOcean

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.DO_HOST }}
          username: ${{ secrets.DO_USER }}
          key: ${{ secrets.DO_SSH_KEY }}
          script: |
            cd /var/www/DanesAppStudio
            git pull origin main
            # Add specific restart commands here
```

## 🔐 Security Checks (Git-Ops)
- **Never** commit `.env` files to Git.
- Add all production secrets (GHL Tokens, DB Passwords) to **GitHub Actions Secrets** (for the backend) and **Vercel Environment Variables** (for the frontend).
- Use **DigitalOcean Reserved IPs** to ensure your server IP doesn't change after a reboot.

## ⚡ Verification
After pushing, verify the deployment:
1. Check GitHub "Actions" tab for a green checkmark.
2. Check the Vercel Dashboard for "Deployment: Ready".
3. Confirm the live URL (e.g., `client1.larkinauto.com`) reflects the latest changes.
