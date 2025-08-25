from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('metrics', '0002_initial'),
    ]

    operations = [
        migrations.RunSQL(
            """
            -- Enable the extension if not already enabled
            CREATE EXTENSION IF NOT EXISTS timescaledb;

            -- Convert MetricValue table into a hypertable
            SELECT create_hypertable(
                'metrics_metricvalue',   -- table name
                'time',             -- time column
                chunk_time_interval => interval '1 day',
                if_not_exists => TRUE
            );

            -- Enable compression on the hypertable
            ALTER TABLE metrics_metricvalue SET (
                timescaledb.compress,
                timescaledb.compress_orderby = 'time DESC',
                timescaledb.compress_segmentby = 'metric_id, h3_index'
            );

            -- Add a compression policy: compress chunks older than 1 day
            SELECT add_compression_policy(
                'metrics_metricvalue',
                INTERVAL '1 day'
            );
            """,
            reverse_sql="""
            -- Remove compression policy
            SELECT remove_compression_policy('metrics_metricvalue');

            -- Disable compression
            ALTER TABLE metrics_metricvalue'); RESET (timescaledb.compress);

            -- NOTE: Hypertable -> normal table conversion isn't directly supported,
            -- so reversing create_hypertable must be handled manually if needed.
            """,
        ),
    ]