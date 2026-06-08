# GitHub Actions Auto Deploy

這份設定會讓 GitHub 在 `main` 分支有新 commit 時自動部署：

- build Docker image
- push image 到 Artifact Registry
- deploy Cloud Run webhook service
- create/update Cloud Run Job

Cloud Scheduler、LINE secrets、Firestore、Artifact Registry、runtime service account 仍是一次性基礎設施，建立過就不用每次重做。

## 1. 建立 GitHub repo secrets

到你的 GitHub repo：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

新增三個 secrets：

```text
GCP_PROJECT_ID = linenotify-498803
GCP_REGION = asia-east1
GCP_WORKLOAD_IDENTITY_PROVIDER = setup script 印出的 provider resource name
```

這個流程使用 Workload Identity Federation，不需要建立或保存 service account JSON key。

## 2. 建立 GitHub deploy service account

在 Google Cloud Shell 執行：

```bash
cd /home/tlting0311/ndx-sma200-line-alert
GITHUB_REPOSITORY=YOUR_GITHUB_USER/YOUR_REPO bash scripts/setup-github-actions-gcp.sh
```

例如 repo 是 `tlting0311/ndx-sma200-line-alert`：

```bash
GITHUB_REPOSITORY=tlting0311/ndx-sma200-line-alert bash scripts/setup-github-actions-gcp.sh
```

跑完會印出：

```text
GCP_WORKLOAD_IDENTITY_PROVIDER = projects/.../locations/global/workloadIdentityPools/github/providers/github
```

把等號右邊整段貼到 GitHub secret `GCP_WORKLOAD_IDENTITY_PROVIDER`。

## 3. 推到 GitHub

如果你還沒建立 GitHub repo，先在 GitHub 建一個空 repo，然後在 Cloud Shell 或你的 Mac 執行：

```bash
git init
git branch -M main
git add .
git commit -m "Add NDX SMA200 LINE alert"
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

之後每次更新程式：

```bash
git add .
git commit -m "Update alert app"
git push
```

GitHub Actions 就會自動部署。

## 4. LINE webhook URL

第一次 workflow 成功後，到 GitHub Actions 的 log 找：

```text
Webhook URL: https://.../line/webhook
```

把它貼回 LINE Developers Console：

```text
Messaging API -> Webhook URL
```

然後打開 `Use webhook` 並按 `Verify`。
