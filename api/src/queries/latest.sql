select
    coalesce(
        (
            select
                to_json({
                    day: last_day,
                    ended: strftime(ended at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ'),
                    outcome: outcome,
                    rows: rows
                })::varchar
            from runs
            where source = 'yahoo' and outcome = 'stored'
            order by ended desc
            limit 1
        ),
        'null'
    ) as body;
