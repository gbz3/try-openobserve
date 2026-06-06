# try-openobserve

Docker Composeを使用したOpenObserveの立ち上げと、Python（OpenTelemetry SDK）からログおよびトレースを送信して動作確認を行うための全手順です。

---

## 構成概要

この構成では、PythonアプリケーションからOpenTelemetry Protocol (OTLP/HTTP) を使用して、OpenObserveへ直接ログとトレースを送信します。OpenObserveはOTLP入力をネイティブにサポートしているため、今回は中間にOtel Collectorを挟まない最小限の構成で構築します。

```
[ Python Application ] 
       │ (OTLP/HTTP)
       ▼
[ OpenObserve (Docker) ] ── (Port 5080) ──> Web UI 画面

```

---

## 1. ディレクトリ構造

作業用ディレクトリを作成し、以下の構造でファイルを配置します。

```text
openobserve-demo/
├── docker-compose.yml
├── requirements.txt
└── main.py

```

---

## 2. 設定ファイルの作成

### docker-compose.yml

OpenObserveを起動するための設定です。データの永続化領域として `openobserve_data` ボリュームを定義しています。

```yaml
services:
  openobserve:
    image: openobserve/openobserve:v0.10.4
    container_name: openobserve
    environment:
      - ZO_ROOT_USER_EMAIL=admin@example.com
      - ZO_ROOT_USER_PASSWORD=ComplexPassword123!
    ports:
      - "5080:5080"
    volumes:
      - openobserve_data:/data
    restart: unless-stopped

volumes:
  openobserve_data:

```

### requirements.txt

OpenTelemetryのPython用SDK一式と、HTTP通信に必要なライブラリを指定します。

```text
opentelemetry-api==1.24.0
opentelemetry-sdk==1.24.0
opentelemetry-exporter-otlp-proto-http==1.24.0

```

### main.py

ログとトレースを生成し、OpenObserveに送信する検証用スクリプトです。コンテキストの伝播（Trace IDとLogの紐付け）も含めています。

```python
import logging
import time
from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# 1. 共通リソースの設定（サービス名の定義）
resource = Resource.create(attributes={
    "service.name": "python-demo-service",
    "environment": "development"
})

# 2. トレース（Trace）の設定
provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(
    OTLPSpanExporter(endpoint="http://localhost:5080/api/default/v1/traces")
)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# 3. ログ（Log）の設定
logger_provider = LoggerProvider(resource=resource)
log_processor = BatchLogRecordProcessor(
    OTLPLogExporter(endpoint="http://localhost:5080/api/default/v1/logs")
)
logger_provider.add_log_record_processor(log_processor)
set_logger_provider(logger_provider)

# 標準のloggingライブラリとOpenTelemetryを結びつけるハンドラーを設定
handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def main():
    print("Sending telemetry data to OpenObserve...")

    # スパン（トレースの区切り）の開始
    with tracer.start_as_current_span("main-operation") as span:
        span.set_attribute("custom.metric", "test-value")
        
        logger.info("アプリケーションの処理を開始しました。")
        
        # 擬似的なネストされた処理
        with tracer.start_as_current_span("sub-operation"):
            logger.warning("サブルーチン内で警告が発生した想定のログです。")
            time.sleep(0.5)
            
        logger.info("すべての処理が正常に終了しました。")

    # バッファに残っているデータを確実に送信
    provider.shutdown()
    logger_provider.shutdown()
    print("Done.")


if __name__ == "__main__":
    main()

```

---

## 3. 手順

### ステップ 1: OpenObserve の起動

ターミナルで対象ディレクトリに移動し、Dockerコンテナをバックグラウンドで起動します。

```bash
docker compose up -d

```

起動後、ブラウザで `http://localhost:5080` にアクセスします。
ログイン画面が表示されるので、`docker-compose.yml` に設定した以下のクレデンシャルでログインします。

* **User Email:** `admin@example.com`
* **Password:** `ComplexPassword123!`

### ステップ 2: Python 環境の準備と実行

別のターミナルウィンドウ（または仮想環境）で、必要なパッケージをインストールしてスクリプトを実行します。

```bash
# 必要に応じて仮想環境を作成 (python3 -m venv .venv && source .venv/bin/activate)
pip install -r requirements.txt

# スクリプトの実行
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic%20$(printf '%s' 'a
dmin@example.com:ComplexPassword123!' | base64 -w0)" && python3 main.py

```

実行後、画面に `Sending telemetry data to OpenObserve...` および `Done.` と表示されれば送信完了です。

### ステップ 3: OpenObserve 画面での確認

1. **ログの確認:**
* OpenObserveの左メニューから **[Logs]** を選択します。
* ストリーム（テーブル）の一覧から `default` または `python-demo-service` に関連するログを選択すると、送信された `INFO` や `WARNING` のログがタイムスタンプ付きで確認できます。


2. **トレースの確認:**
* 左メニューから **[Traces]** を選択します。
* `main-operation` や `sub-operation` という名前のスパンが表示され、それぞれの処理にかかった時間（タイムライン）がタイムチャート形式で可視化されます。
* ログ内に含まれる `trace_id` を介して、どのログがどのトレースの最中に出力されたものかを追跡できます。
