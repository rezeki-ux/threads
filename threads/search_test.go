package threads

import "testing"

// A search-style SSR block: two distinct posts plus one duplicate of the first
// post (same pk) in a second data-sjs block, mirroring how the search page can
// repeat a record. The parser must deduplicate by pk and extract the fields
// SearchResult maps from.
const searchFixtureHTML = `<html><head><title>Search</title></head><body>
<script type="application/json" data-sjs>
{"require":[["X","next",[],[{"__bbox":{"result":{"data":{"xdt_api__v1__search__threads_connection":{
  "thread_items":[
    {"post":{"pk":"900","code":"SRC1","caption":{"text":"first AI hit"},"taken_at":1700000000,
      "like_count":5,"media_type":1,"user":{"pk":"10","username":"alice"},
      "text_post_app_info":{"direct_reply_count":1,"repost_count":0,"quote_count":0}}},
    {"post":{"pk":"901","code":"SRC2","caption":{"text":"second AI hit"},"taken_at":1700000100,
      "like_count":7,"media_type":2,"user":{"pk":"11","username":"bob"},
      "text_post_app_info":{"direct_reply_count":0,"repost_count":1,"quote_count":0}}}
  ],
  "page_info":{"end_cursor":null,"has_next_page":false}}}}}}]]]}
</script>
<script type="application/json" data-sjs>
{"require":[["Y","next",[],[{"__bbox":{"result":{"data":{
  "thread_items":[
    {"post":{"pk":"900","code":"SRC1","caption":{"text":"first AI hit"},"taken_at":1700000000,
      "like_count":5,"media_type":1,"user":{"pk":"10","username":"alice"},
      "text_post_app_info":{"direct_reply_count":1,"repost_count":0,"quote_count":0}}}
  ]
}}}}}]]]}
</script>
</body></html>`

func TestParsePostsSSRSearchDedup(t *testing.T) {
	posts := parsePostsSSR(searchFixtureHTML)
	if len(posts) != 2 {
		t.Fatalf("want 2 deduplicated posts, got %d", len(posts))
	}
	byID := map[string]Post{}
	for _, p := range posts {
		byID[p.ID] = p
	}
	if _, ok := byID["900"]; !ok {
		t.Error("missing post 900")
	}
	if _, ok := byID["901"]; !ok {
		t.Error("missing post 901")
	}
	p := byID["900"]
	if p.Text != "first AI hit" || p.Username != "alice" {
		t.Errorf("post 900 fields: %+v", p)
	}
	if p.Permalink != WebBase+"/@alice/post/SRC1" {
		t.Errorf("post 900 permalink: %q", p.Permalink)
	}
	if p.Timestamp.IsZero() {
		t.Error("post 900 timestamp should be set")
	}
}

func TestValidateSearchType(t *testing.T) {
	cases := []struct {
		in      string
		wantErr bool
	}{
		{"", false},
		{"top", false},
		{"recent", true},
		{"RECENT", true},
		{"garbage", true},
	}
	for _, tc := range cases {
		err := validateSearchType(tc.in)
		if (err != nil) != tc.wantErr {
			t.Errorf("validateSearchType(%q) err=%v, wantErr=%v", tc.in, err, tc.wantErr)
		}
		if err != nil && Code(err) != ExitUsage {
			t.Errorf("validateSearchType(%q) code=%d, want ExitUsage", tc.in, Code(err))
		}
	}
}

func TestIsStaleGraphQLError(t *testing.T) {
	cases := []struct {
		name string
		errs []graphqlError
		want bool
	}{
		{"missing_required_variable_value message", []graphqlError{{Message: "A server error missing_required_variable_value occurred"}}, true},
		{"code 1675012", []graphqlError{{Code: 1675012}}, true},
		{"ordinary error", []graphqlError{{Message: "rate limited"}}, false},
		{"empty", nil, false},
	}
	for _, tc := range cases {
		if got := isStaleGraphQLError(tc.errs); got != tc.want {
			t.Errorf("%s: isStaleGraphQLError = %v, want %v", tc.name, got, tc.want)
		}
	}
}

// A page with no thread_items parses to zero posts, not an error.
func TestParsePostsSSREmpty(t *testing.T) {
	if posts := parsePostsSSR("<html><body>no posts here</body></html>"); len(posts) != 0 {
		t.Errorf("empty page must parse to 0 posts, got %d", len(posts))
	}
}

// A reply post with structured fragments and a mention/quote carries the richer
// metadata: mentions, hashtags, reply authorship, reshare count, and quote id.
const richPostHTML = `<html><body>
<script type="application/json" data-sjs>
{"thread_items":[{"post":{
  "pk":"700","code":"RICH","caption":{"text":"cc @alice and @bob #golang #threads"},
  "taken_at":1700000000,"like_count":9,"media_type":1,
  "original_width":1080,"original_height":1350,
  "user":{"pk":"20","username":"carol","full_name":"Carol","is_verified":true,"profile_pic_url":"http://x/p.jpg"},
  "text_post_app_info":{
    "direct_reply_count":3,"repost_count":2,"quote_count":1,"reshare_count":4,
    "is_reply":true,
    "reply_to_author":{"id":"30","username":"alice"},
    "share_info":{"quoted_post":{"pk":"999"}},
    "text_fragments":{"fragments":[
      {"fragment_type":"plaintext","plaintext":"cc "},
      {"fragment_type":"mention","mention_fragment":{"mentioned_user":{"username":"alice","id":"30"}},"plaintext":"@alice"},
      {"fragment_type":"mention","mention_fragment":{"mentioned_user":{"username":"bob","id":"31"}},"plaintext":"@bob"}
    ]}
  }
}}]}
</script>
</body></html>`

func TestParsePostRichMetadata(t *testing.T) {
	posts := parsePostsSSR(richPostHTML)
	if len(posts) != 1 {
		t.Fatalf("want 1 post, got %d", len(posts))
	}
	p := posts[0]
	if p.AuthorName != "Carol" || !p.AuthorVerified || p.AuthorAvatarURL != "http://x/p.jpg" {
		t.Errorf("author fields: name=%q verified=%v avatar=%q", p.AuthorName, p.AuthorVerified, p.AuthorAvatarURL)
	}
	if p.Width != 1080 || p.Height != 1350 {
		t.Errorf("dimensions: %dx%d", p.Width, p.Height)
	}
	if p.ReshareCount != 4 {
		t.Errorf("reshare_count = %d, want 4", p.ReshareCount)
	}
	if !p.IsReply || p.ReplyToID != "30" || p.ReplyToUsername != "alice" {
		t.Errorf("reply linkage: is_reply=%v to=%q/%q", p.IsReply, p.ReplyToID, p.ReplyToUsername)
	}
	if !p.IsQuotePost || p.QuotedPostID != "999" {
		t.Errorf("quote: is_quote=%v id=%q", p.IsQuotePost, p.QuotedPostID)
	}
	if len(p.Mentions) != 2 || p.Mentions[0] != "alice" || p.Mentions[1] != "bob" {
		t.Errorf("mentions = %v", p.Mentions)
	}
	if len(p.Hashtags) != 2 || p.Hashtags[0] != "golang" || p.Hashtags[1] != "threads" {
		t.Errorf("hashtags = %v", p.Hashtags)
	}
}
