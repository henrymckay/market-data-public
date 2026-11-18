create table alerts (
    id varchar,
    kind varchar,
    message varchar,
    sent timestamp with time zone,
    title varchar
);

create table alert_state (
    changed timestamp with time zone,
    detail varchar,
    key varchar,
    state varchar
);
