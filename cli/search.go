package cli

import (
	"strings"

	"github.com/spf13/cobra"
)

func newSearchCmd(a *App) *cobra.Command {
	var typ string
	cmd := &cobra.Command{
		Use:   "search <query>",
		Short: "Keyword search across public posts",
		Long: `Read the anonymous, server-rendered search results page for a keyword.

Search results are served as static HTML to the crawler user agent, so no login
and no persisted GraphQL id (doc_id) is required. --type is accepted for
compatibility; only "top" maps to the default anonymous surface today.`,
		Args: minArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			defer func() { _ = a.Out.Flush() }()
			ctx := cmd.Context()
			query := strings.Join(args, " ")
			a.progress("searching %q", query)
			for r, err := range a.Client.Search(ctx, query, typ, a.Limit) {
				if err != nil {
					return err
				}
				if err := a.Out.Emit(searchRow(&r)); err != nil {
					return err
				}
			}
			return nil
		},
	}
	cmd.Flags().StringVar(&typ, "type", "top", "top|recent")
	return cmd
}
