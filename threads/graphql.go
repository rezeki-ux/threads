package threads

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"maps"
	"net/http"
	"net/url"
	"strings"
)

// The logged-out GraphQL path. Threads marks a caller as a crawler through a set
// of relay provider flags; with those set, the persisted profile-threads, post,
// and search queries return data without a session. doc_id values rotate (see
// config.go), so a stale id degrades to "no extra data" rather than an error.

func relayProviderVars() map[string]any {
	return map[string]any{
		"__relay_internal__pv__BarcelonaIsLoggedInrelayprovider":             false,
		"__relay_internal__pv__BarcelonaIsInternalUserrelayprovider":         false,
		"__relay_internal__pv__BarcelonaIsCrawlerrelayprovider":              true,
		"__relay_internal__pv__BarcelonaOptionalCookiesEnabledrelayprovider": true,
		"__relay_internal__pv__BarcelonaIsLoggedOutrelayprovider":            true,
	}
}

// maxGraphQLPages caps how far the logged-out pagination walks, so an unbounded
// crawl cannot loop forever on a profile with a very long history.
const maxGraphQLPages = 20

// graphqlProfileThreads walks a user's posts via the logged-out persisted query,
// following the page_info cursor from startCursor until it runs out or the page
// cap is hit. startCursor is the end_cursor from the server-rendered window, so
// pagination resumes where the SSR page left off.
func (c *Client) graphqlProfileThreads(ctx context.Context, userID, startCursor string) ([]Post, error) {
	var out []Post
	cursor := startCursor
	for page := 0; page < maxGraphQLPages; page++ {
		vars := map[string]any{"userID": userID}
		if cursor != "" {
			vars["after"] = cursor
		}
		raw, err := c.graphqlPost(ctx, c.cfg.DocIDProfileThreads, vars)
		if err != nil {
			return out, err
		}
		out = append(out, postsFromGraphQL(raw)...)
		next, more, ok := findPageInfo(raw, 0)
		if !ok || !more || next == "" || next == cursor {
			break
		}
		cursor = next
	}
	return out, nil
}

// graphqlPostReplies fetches a window of a post's replies via the logged-out
// persisted query.
func (c *Client) graphqlPostReplies(ctx context.Context, postID string) ([]Post, error) {
	vars := map[string]any{"postID": postID}
	raw, err := c.graphqlPost(ctx, c.cfg.DocIDPostPage, vars)
	if err != nil {
		return nil, err
	}
	return postsFromGraphQL(raw), nil
}

// graphqlPost POSTs a persisted query and returns the decoded data tree. The
// error is classified so callers (and the user) can tell a network failure, an
// HTML/login-wall answer, a GraphQL "errors" payload, null data, and a shape
// change apart instead of everything collapsing into "doc_id may be stale".
func (c *Client) graphqlPost(ctx context.Context, docID string, vars map[string]any) (any, error) {
	maps.Copy(vars, relayProviderVars())
	varsJSON, _ := json.Marshal(vars)
	form := url.Values{}
	form.Set("lsd", "t")
	form.Set("doc_id", docID)
	form.Set("variables", string(varsJSON))

	c.rateLimit()
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, GraphQLURL, strings.NewReader(form.Encode()))
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", c.cfg.UserAgent)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("X-FB-LSD", "t")
	req.Header.Set("X-IG-App-ID", "238260118697367")
	if c.cfg.Session != "" {
		req.Header.Set("Cookie", "sessionid="+c.cfg.Session)
	}
	if c.cfg.CSRF != "" {
		req.Header.Set("X-CSRFToken", c.cfg.CSRF)
	}

	c.logf(2, "POST %s doc_id=%s vars=%s", GraphQLURL, docID, truncateBytes(varsJSON, 512))
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, codeErr(ExitNetwork, "graphql request: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	ctype := resp.Header.Get("Content-Type")
	c.logf(2, "graphql resp status=%d content-type=%q bytes=%d", resp.StatusCode, ctype, len(body))

	if resp.StatusCode == 429 || resp.StatusCode == 503 {
		return nil, codeErr(ExitRateLimit, "graphql rate limited (HTTP %d)", resp.StatusCode)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, codeErr(ExitNetwork, "graphql HTTP %d (content-type %q)", resp.StatusCode, ctype)
	}

	// A non-JSON answer means the request was routed to the app shell (HTML)
	// rather than the API, e.g. the endpoint rejected the request before GraphQL
	// ran. Surface what came back instead of pretending it is a JSON shape issue.
	if !strings.Contains(ctype, "json") && !strings.Contains(ctype, "javascript") && !strings.Contains(ctype, "text") {
		c.logf(2, "graphql body[%d] = %s", len(body), truncateBytes(body, 512))
		return nil, codeErr(ExitNotFound, "graphql returned %q (status %d), not JSON; the endpoint may be gating this request", ctype, resp.StatusCode)
	}

	var env graphqlEnvelope
	if err := json.Unmarshal(body, &env); err != nil {
		c.logf(2, "graphql body[%d] = %s", len(body), truncateBytes(body, 512))
		return nil, codeErr(ExitNotFound, "graphql returned non-JSON (status %d, content-type %q); the doc_id may be stale", resp.StatusCode, ctype)
	}

	if len(env.Errors) > 0 {
		seen := map[string]bool{}
		msgs := make([]string, 0, len(env.Errors))
		for _, e := range env.Errors {
			m := e.Message
			if m == "" {
				m = e.Summary
			}
			if m == "" {
				m = e.Description
			}
			if m == "" {
				m = fmt.Sprintf("code %d", e.Code)
			}
			if seen[m] {
				continue
			}
			seen[m] = true
			msgs = append(msgs, m)
		}
		if isStaleGraphQLError(env.Errors) {
			return nil, codeErr(ExitOperationStale, "graphql operation is stale: %s", strings.Join(msgs, "; "))
		}
		return nil, codeErr(ExitNotFound, "graphql error: %s", strings.Join(msgs, "; "))
	}

	if len(env.Data) == 0 || string(env.Data) == "null" {
		return nil, codeErr(ExitNotFound, "graphql returned null data (doc_id %s may be stale, or anonymous search is gated)", docID)
	}

	var data any
	if err := json.Unmarshal(env.Data, &data); err != nil {
		return nil, codeErr(ExitNotFound, "graphql data has an unexpected shape")
	}
	return data, nil
}

// graphqlEnvelope is the outer GraphQL response wrapper Threads returns.
type graphqlEnvelope struct {
	Data   json.RawMessage `json:"data"`
	Errors []graphqlError  `json:"errors"`
}

type graphqlError struct {
	Message     string `json:"message"`
	Severity    string `json:"severity"`
	Code        int    `json:"code"`
	Summary     string `json:"summary"`
	Description string `json:"description"`
}

// isStaleGraphQLError reports whether a GraphQL errors payload indicates the
// persisted query behind a doc_id has been rotated. Code 1675012 and the
// "missing_required_variable_value" message are the signatures Threads returns
// when a doc_id maps to a query whose required variables no longer match.
func isStaleGraphQLError(errs []graphqlError) bool {
	for _, e := range errs {
		if e.Code == 1675012 {
			return true
		}
		if strings.Contains(strings.ToLower(e.Message), "missing_required_variable_value") {
			return true
		}
	}
	return false
}

// truncateBytes clips a byte slice to n bytes for safe diagnostics output.
func truncateBytes(b []byte, n int) string {
	if len(b) <= n {
		return string(b)
	}
	return string(b[:n]) + "..."
}

// postsFromGraphQL reuses the SSR thread_items walker over the GraphQL data
// tree: both surfaces nest the same post objects.
func postsFromGraphQL(data any) []Post {
	posts := walkThreadItems(data, 0)
	out := posts[:0]
	seen := map[string]bool{}
	for _, p := range posts {
		if p.ID == "" || seen[p.ID] {
			continue
		}
		seen[p.ID] = true
		out = append(out, p)
	}
	return out
}
