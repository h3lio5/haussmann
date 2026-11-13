create table if not exists runs (
    id text primary key,
    inputs_digest text not null,
    created_at timestamptz not null default now()
);

create table if not exists steps (
    run_id text not null references runs (id),
    key text not null,
    seq integer not null,
    result jsonb not null,
    done_at timestamptz not null default now(),
    primary key (run_id, key)
);

create table if not exists ledger_entries (
    run_id text not null references runs (id),
    tx integer not null,
    position integer not null,
    step text not null,
    entry jsonb not null,
    primary key (run_id, tx, position)
);

create table if not exists calls (
    n bigint generated always as identity,
    run_id text not null references runs (id),
    key text not null,
    step text not null,
    model text not null,
    input_tokens integer not null,
    output_tokens integer not null,
    cost_usd numeric not null,
    response jsonb not null,
    at timestamptz not null default now(),
    primary key (run_id, key)
);
