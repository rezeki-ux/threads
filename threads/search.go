package threads

import (
	"context"
	"iter"
	"net/url"
	"time"
)

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
// page. It honors limit (0 = unlimited). searchType carries the CLI --type
// flag; anything other than "top" is reported as unsupported rather than
// silently falling back.
func (c *Client) Search(ctx context.Context, query, searchType string, limit int) iter.Seq2[SearchResult, error] {
	return func(yield func(SearchResult, error) bool) {
		if err := validateSearchType(searchType); err != nil {
			yield(SearchResult{}, err)
			return
		}

		// Anonymous SSR search returns a single window (the page reports
		// has_next_page=false and no cursor), so there is no continuation to
		// walk. parsePostsSSR already deduplicates by post id within that
		// window.
		posts, err := c.searchSSR(ctx, query)
		if err != nil {
			yield(SearchResult{}, err)
			return
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
