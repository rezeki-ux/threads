package threads

import (
	"context"
	"iter"
	"net/url"
	"time"
)

// maxSearchPages is the ceiling on search continuation requests. Anonymous SSR
// search returns a single window (the page's page_info reports has_next_page
// false and a null end_cursor), so today the loop runs exactly once. The cap
// exists so a future continuation mechanism can never loop unboundedly.
const maxSearchPages = 20

// searchSSR fetches the server-rendered search results page for a keyword. The
// crawler user agent makes Threads render search results without a session or
// browser, and the records use the same thread_items[].post shape the SSR
// profile/post parser already understands. This is the primary search path:
// it does not depend on any rotating doc_id.
func (c *Client) searchSSR(ctx context.Context, query string) ([]Post, error) {
	target := WebBase + "/search?q=" + url.QueryEscape(query)
	html, err := c.getHTML(ctx, target)
	if err != nil {
		return nil, err
	}
	return parsePostsSSR(html), nil
}

// validateSearchType returns nil for the supported anonymous search sorts and
// a clear error for anything else. Only the default ("top") surface is served
// anonymously; Threads does not expose a "recent" sort to anonymous crawlers.
func validateSearchType(t string) error {
	switch t {
	case "", "top":
		return nil
	default:
		return codeErr(ExitUsage, "search type %q is not supported for anonymous Threads search", t)
	}
}

// Search streams keyword search hits from the anonymous server-rendered search
// page. It deduplicates by post id and honors limit (0 = unlimited). searchType
// carries the CLI --type flag; anything other than "top" is reported as
// unsupported rather than silently falling back.
func (c *Client) Search(ctx context.Context, query, searchType string, limit int) iter.Seq2[SearchResult, error] {
	return func(yield func(SearchResult, error) bool) {
		if err := validateSearchType(searchType); err != nil {
			yield(SearchResult{}, err)
			return
		}

		var posts []Post
		seen := map[string]bool{}
		for page := 0; page < maxSearchPages; page++ {
			window, err := c.searchSSR(ctx, query)
			if err != nil {
				yield(SearchResult{}, err)
				return
			}
			if len(window) == 0 {
				break
			}
			added := 0
			for _, p := range window {
				if p.ID == "" || seen[p.ID] {
					continue
				}
				seen[p.ID] = true
				posts = append(posts, p)
				added++
			}
			if added == 0 {
				// No new posts in this window; a future continuation would only
				// repeat what we already have, so stop.
				break
			}
			// Anonymous SSR search has no continuation cursor today; this loop
			// runs once. The break keeps a future cursor mechanism honest.
			break
		}

		n := 0
		for _, p := range posts {
			r := SearchResult{
				Post:       p,
				Query:      query,
				SearchedAt: time.Now(),
			}
			if !yield(r, nil) {
				return
			}
			n++
			if limit > 0 && n >= limit {
				return
			}
		}
	}
}
