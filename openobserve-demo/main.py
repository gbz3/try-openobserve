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

