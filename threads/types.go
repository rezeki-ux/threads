package threads

import "time"

// Profile is a Threads user.
type Profile struct {
	ID             string    `json:"id,omitempty"`
	Username       string    `json:"username"`
	Name           string    `json:"name,omitempty"`
	Biography      string    `json:"biography,omitempty"`
	ProfilePicURL  string    `json:"profile_pic_url,omitempty"`
	IsVerified     bool      `json:"is_verified"`
	IsPrivate      bool      `json:"is_private,omitempty"`
	ExternalURL    string    `json:"external_url,omitempty"`
	FollowerCount  int64     `json:"follower_count,omitempty"`
	FollowingCount int64     `json:"following_count,omitempty"`
	URL            string    `json:"url"`
	FetchedAt      time.Time `json:"fetched_at"`
}

// Post is a single Threads post. Every field is taken verbatim from the
// server-rendered post object; a field Threads does not surface anonymously is
// left at its zero value rather than guessed.
type Post struct {
	ID                string    `json:"id"`
	Shortcode         string    `json:"shortcode,omitempty"`
	Text              string    `json:"text,omitempty"`
	MediaType         string    `json:"media_type,omitempty"` // TEXT_POST, IMAGE, VIDEO, CAROUSEL_ALBUM
	MediaURLs         []string  `json:"media_urls,omitempty"`
	Permalink         string    `json:"permalink,omitempty"`
	CanonicalURL      string    `json:"canonical_url,omitempty"`
	Username          string    `json:"username,omitempty"`
	UserID            string    `json:"user_id,omitempty"`
	AuthorName        string    `json:"author_name,omitempty"`
	AuthorVerified    bool      `json:"author_verified,omitempty"`
	AuthorAvatarURL   string    `json:"author_avatar_url,omitempty"`
	Timestamp         time.Time `json:"timestamp,omitempty"`
	LikeCount         int64     `json:"like_count"`
	ReplyCount        int64     `json:"reply_count"`
	RepostCount       int64     `json:"repost_count"`
	ReshareCount      int64     `json:"reshare_count,omitempty"`
	QuoteCount        int64     `json:"quote_count"`
	IsQuotePost       bool      `json:"is_quote_post,omitempty"`
	IsReply           bool      `json:"is_reply,omitempty"`
	QuotedPostID      string    `json:"quoted_post_id,omitempty"`
	ReplyToID         string    `json:"reply_to_id,omitempty"`
	ReplyToUsername   string    `json:"reply_to_username,omitempty"`
	Mentions          []string  `json:"mentions,omitempty"`
	Hashtags          []string  `json:"hashtags,omitempty"`
	Width             int       `json:"width,omitempty"`
	Height            int       `json:"height,omitempty"`
	IsPaidPartnership bool      `json:"is_paid_partnership,omitempty"`
	HasAudio          bool      `json:"has_audio,omitempty"`
	HasMedia          bool      `json:"has_media,omitempty"`
	FetchedAt         time.Time `json:"fetched_at"`
}

// Reply is a post in a reply thread. It embeds the full Post so every post
// field is available, and adds the thread linkage. Go flattens the embedded
// Post into the JSON, so the output stays flat and backward compatible.
type Reply struct {
	Post
	ParentID string `json:"parent_id,omitempty"`
	RootID   string `json:"root_id,omitempty"`
}

// SearchResult is one hit from a keyword search. It embeds the full Post for
// consistency with feed/post records and adds the query context.
type SearchResult struct {
	Post
	Query      string    `json:"query"`
	SearchedAt time.Time `json:"searched_at"`
}

// asReply converts a parsed post (a reply lives in the same thread_items shape
// as a post) into a Reply under the given root/parent.
func (p Post) asReply(parentID, rootID string) Reply {
	return Reply{Post: p, ParentID: parentID, RootID: rootID}
}
