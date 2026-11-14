-- Module 1 contract v1, section 3. Add-only: later migrations may add, never drop or rename.
create schema if not exists ingestion;

create table ingestion.sources (
    source_id   text primary key,
    connector   text not null,
    active      boolean not null,
    licence     text not null,
    access_rule text not null,
    credit_line text not null,
    themes      text[] not null,
    definition  jsonb not null,
    updated_at  timestamptz not null default now()
);

create table ingestion.raw_blobs (
    sha256        text primary key check (sha256 ~ '^[0-9a-f]{64}$'),
    media_type    text not null,
    size_bytes    integer not null,
    content       bytea not null,
    first_seen_at timestamptz not null default now()
);

create table ingestion.raw_pulls (
    pull_id            bigint generated always as identity primary key,
    source_id          text not null references ingestion.sources (source_id),
    started_at         timestamptz not null default now(),
    finished_at        timestamptz,
    status             text not null check (status in ('running', 'ok', 'failed')),
    error              text,
    trigger            text not null check (trigger in ('schedule', 'manual')),
    code_version       text not null,
    discovery          jsonb,
    content_checksum   text,
    structure_checksum text,
    row_count          integer,
    changed            boolean not null default false
);
create index raw_pulls_source_ok on ingestion.raw_pulls (source_id, pull_id desc) where status = 'ok';

create table ingestion.raw_pull_files (
    pull_id     bigint not null references ingestion.raw_pulls (pull_id),
    kind        text not null,
    url         text not null,
    http_status integer not null,
    media_type  text not null,
    size_bytes  integer not null,
    sha256      text not null references ingestion.raw_blobs (sha256),
    primary key (pull_id, kind)
);

create table ingestion.staging_batches (
    batch_id   bigint generated always as identity primary key,
    pull_id    bigint not null unique references ingestion.raw_pulls (pull_id),
    source_id  text not null references ingestion.sources (source_id),
    row_count  integer not null,
    checks     jsonb not null,
    status     text not null check (status in ('checks_passed', 'checks_failed')),
    created_at timestamptz not null default now()
);

create table ingestion.staged_rows (
    batch_id   bigint not null references ingestion.staging_batches (batch_id),
    row_no     integer not null,
    dimensions jsonb not null,
    period     text not null,
    value      numeric,
    attributes jsonb not null,
    primary key (batch_id, row_no)
);

create table ingestion.code_labels (
    source_id text not null references ingestion.sources (source_id),
    concept   text not null,
    code      text not null,
    label     text not null,
    pull_id   bigint not null references ingestion.raw_pulls (pull_id),
    primary key (source_id, concept, code)
);

create table ingestion.events (
    event_id          bigint generated always as identity primary key,
    event_type        text not null,
    source_id         text not null references ingestion.sources (source_id),
    pull_id           bigint not null references ingestion.raw_pulls (pull_id),
    previous_pull_id  bigint references ingestion.raw_pulls (pull_id),
    batch_id          bigint not null references ingestion.staging_batches (batch_id),
    initial           boolean not null,
    added             integer not null,
    removed           integer not null,
    revised           integer not null,
    periods_affected  text[] not null,
    structure_changed boolean not null,
    checks_passed     boolean not null,
    created_at        timestamptz not null default now()
);

alter table ingestion.sources enable row level security;
alter table ingestion.raw_blobs enable row level security;
alter table ingestion.raw_pulls enable row level security;
alter table ingestion.raw_pull_files enable row level security;
alter table ingestion.staging_batches enable row level security;
alter table ingestion.staged_rows enable row level security;
alter table ingestion.code_labels enable row level security;
alter table ingestion.events enable row level security;
