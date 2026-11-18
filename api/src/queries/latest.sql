select
    coalesce(
        (
            select
                to_json({
                    day: last_day,
                    ended: strftime(ended at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ'),
                    outcome: outcome,
                    rows: rows,
                    version: (
                        select
                            strftime(
                                max(metrics_runs.ended) at time zone 'UTC',
                                '%Y-%m-%dT%H:%M:%SZ'
                            )
                        from runs as metrics_runs
                        where
                            metrics_runs.source = 'metrics'
                            and metrics_runs.outcome = 'stored'
                    )
                })::varchar
            from runs
            where source = 'yahoo' and outcome = 'stored'
            order by ended desc
            limit 1
        ),
        'null'
    ) as body;
