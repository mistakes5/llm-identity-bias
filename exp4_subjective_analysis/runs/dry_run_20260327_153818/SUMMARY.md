# Summary

Status: completed dry run.

- Coverage: 50/50 raw responses, 50 judge files, analysis outputs, and plots are present.
- Strong automated profile effects appeared in `response_length`, `estimated_tokens`, `cross_domain_count`, `paragraph_count`, and `unique_entity_count`.
- The biggest separations were high-vs-low profile contrasts. Mean estimated tokens were A `1121.3`, D `1058.7`, B `650.7`, E `499.4`, and C `461.5`.
- Cross-domain references also separated cleanly: D `2.4`, A `1.9`, B `1.3`, C `0.7`, E `0.7`.
- Sonnet showed more sensitivity to profile priming than haiku in the statistical report.

Caveat: the judge-derived rubric metrics did not survive cleanly into the dry-run statistical tables, so the clearest signal in this run comes from the automated text metrics rather than the rubric columns.

Primary sources for this summary:

- `analysis/summary_report.txt`
- `results/metrics/metrics_table.csv`
