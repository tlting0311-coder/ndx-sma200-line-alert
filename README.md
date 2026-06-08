# Nasdaq 100 SMA200 LINE Alert

這個專案會在 Nasdaq 100 (`^NDX`) 收盤價「穿越」200 日 SMA 時，透過 LINE Messaging API 私訊所有已訂閱使用者：

- 收盤價由 SMA200 下方穿上去：買入訊號
- 收盤價由 SMA200 上方跌破：賣出訊號
- 同一個交易日同一個訊號只通知一次

LINE Notify 已於 2025-03-31 終止，因此本專案使用 LINE Official Account + Messaging API。

## Local Commands

```bash
python -m ndx_signal check --dry-run
python -m ndx_signal check --send
```

`--dry-run` 會讀取行情、計算訊號、列出訂閱人數，但不發送 LINE。`--send` 會在新訊號出現時推播。

## Required Configuration

環境變數：

```bash
SYMBOL=^NDX
SMA_WINDOW=200
TIMEZONE=Asia/Taipei
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
```

Secret Manager：

```bash
LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET
```

Firestore 會使用下列集合：

- `subscriptions/{userId}`：訂閱者狀態
- `app_state/latest_signal`：最新完成通知的訊號
- `signals/{signalKey}/deliveries/{userId}`：單一訊號的逐人發送結果

## LINE Setup

1. 建立 LINE Official Account。
2. 在 LINE Developers Console 啟用 Messaging API。
3. 取得 long-lived channel access token，放入 `LINE_CHANNEL_ACCESS_TOKEN`。
4. 取得 channel secret，放入 `LINE_CHANNEL_SECRET`。
5. 部署 Cloud Run webhook service 後，把 webhook URL 設成：

```text
https://YOUR_CLOUD_RUN_SERVICE_URL/line/webhook
```

6. 在 Messaging API 頁面啟用 `Use webhook`。
7. 使用者加入官方帳號後，傳送：

```text
訂閱
```

可用指令：

- `訂閱`：加入通知
- `取消`：取消通知
- `狀態`：查詢目前是否訂閱

## Google Cloud Deployment

以下範例使用 `asia-east1`。請先安裝並登入 `gcloud`。

若要改用 GitHub 自動部署，請看 [docs/github-actions-deploy.md](docs/github-actions-deploy.md)。

```bash
PROJECT_ID=your-gcp-project-id
REGION=asia-east1
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/ndx-signal/ndx-signal:latest"
RUN_SA="ndx-signal-run@$PROJECT_ID.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"

gcloud services enable \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com

gcloud iam service-accounts create ndx-signal-run \
  --display-name="NDX signal Cloud Run runtime"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$RUN_SA" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$RUN_SA" \
  --role="roles/secretmanager.secretAccessor"
```

建立 Firestore database，選 Native mode。若專案尚未建立 database：

```bash
gcloud firestore databases create --location="$REGION"
```

建立 secrets：

```bash
printf "YOUR_LINE_CHANNEL_ACCESS_TOKEN" | \
  gcloud secrets create line-channel-access-token --data-file=-

printf "YOUR_LINE_CHANNEL_SECRET" | \
  gcloud secrets create line-channel-secret --data-file=-
```

建立 Artifact Registry 並建置 image：

```bash
gcloud artifacts repositories create ndx-signal \
  --repository-format=docker \
  --location="$REGION"

gcloud builds submit --tag "$IMAGE"
```

部署 webhook service：

```bash
gcloud run deploy ndx-signal-webhook \
  --image "$IMAGE" \
  --region "$REGION" \
  --service-account "$RUN_SA" \
  --allow-unauthenticated \
  --set-env-vars "SYMBOL=^NDX,SMA_WINDOW=200,TIMEZONE=Asia/Taipei,GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
  --set-secrets "LINE_CHANNEL_ACCESS_TOKEN=line-channel-access-token:latest,LINE_CHANNEL_SECRET=line-channel-secret:latest"
```

建立每日檢查 job：

```bash
gcloud run jobs create ndx-signal-check \
  --image "$IMAGE" \
  --region "$REGION" \
  --service-account "$RUN_SA" \
  --command=python \
  --args="-m,ndx_signal,check,--send" \
  --set-env-vars "SYMBOL=^NDX,SMA_WINDOW=200,TIMEZONE=Asia/Taipei,GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
  --set-secrets "LINE_CHANNEL_ACCESS_TOKEN=line-channel-access-token:latest"
```

手動測試 job：

```bash
gcloud run jobs execute ndx-signal-check --region "$REGION" --wait
```

設定 Cloud Scheduler，每週二到週六台北時間 06:10 執行，避開美股收盤前：

```bash
gcloud run jobs add-iam-policy-binding ndx-signal-check \
  --region "$REGION" \
  --member="serviceAccount:$RUN_SA" \
  --role="roles/run.invoker"

gcloud scheduler jobs create http ndx-signal-check-schedule \
  --location "$REGION" \
  --schedule "10 6 * * 2-6" \
  --time-zone "Asia/Taipei" \
  --uri "https://run.googleapis.com/v2/projects/$PROJECT_ID/locations/$REGION/jobs/ndx-signal-check:run" \
  --http-method POST \
  --oauth-service-account-email "$RUN_SA"
```

## Tests

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
```

測試涵蓋 SMA 穿越訊號、去重、多使用者推播、LINE webhook 簽章驗證與訂閱指令。
