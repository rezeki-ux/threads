-- Threads scraping storage schema (PostgreSQL).
--
-- `external_id` is the platform-level Threads id (post pk / user pk), used as
-- the natural key for idempotent upserts. `raw_payload` preserves the full Go
-- JSON record as JSONB so fields not yet normalized are never lost.

CREATE TABLE IF NOT EXISTS posts (
    id                  BIGSERIAL PRIMARY KEY,
    platform            TEXT        NOT NULL,
    external_id         TEXT        NOT NULL,
    shortcode           TEXT,
    text                TEXT,
    username            TEXT,
    user_id             TEXT,
    author_name         TEXT,
    author_verified     BOOLEAN,
    author_avatar_url   TEXT,
    timestamp           TIMESTAMPTZ,
    permalink           TEXT,
    canonical_url       TEXT,
    media_type          TEXT,
    media_urls          JSONB,
    like_count          BIGINT      NOT NULL DEFAULT 0,
    reply_count         BIGINT      NOT NULL DEFAULT 0,
    repost_count        BIGINT      NOT NULL DEFAULT 0,
    quote_count         BIGINT      NOT NULL DEFAULT 0,
    is_reply            BOOLEAN     NOT NULL DEFAULT FALSE,
    reply_to_id         TEXT,
    reply_to_username   TEXT,
    quoted_post_id      TEXT,
    is_quote_post       BOOLEAN     NOT NULL DEFAULT FALSE,
    mentions            JSONB,
    hashtags            JSONB,
    width               INTEGER,
    height              INTEGER,
    is_paid_partnership BOOLEAN     NOT NULL DEFAULT FALSE,
    has_audio           BOOLEAN     NOT NULL DEFAULT FALSE,
    parent_id           TEXT,
    root_id             TEXT,
    raw_payload         JSONB,
    fetched_at          TIMESTAMPTZ,
    scraped_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, external_id)
);

CREATE TABLE IF NOT EXISTS profiles (
    id              BIGSERIAL PRIMARY KEY,
    platform        TEXT        NOT NULL,
    external_id     TEXT        NOT NULL,
    username        TEXT,
    name            TEXT,
    biography       TEXT,
    profile_pic_url TEXT,
    is_verified     BOOLEAN     NOT NULL DEFAULT FALSE,
    is_private      BOOLEAN     NOT NULL DEFAULT FALSE,
    external_url    TEXT,
    follower_count  BIGINT      NOT NULL DEFAULT 0,
    following_count BIGINT      NOT NULL DEFAULT 0,
    url             TEXT,
    raw_payload     JSONB,
    fetched_at      TIMESTAMPTZ,
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, external_id)
);

CREATE INDEX IF NOT EXISTS idx_posts_platform_username ON posts (platform, username);
CREATE INDEX IF NOT EXISTS idx_posts_timestamp ON posts (timestamp);
