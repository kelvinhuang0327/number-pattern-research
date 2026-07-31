        # P380 Big Lotto no-DB regression archive query

        ## Scope

        Historical descriptive evidence only. No future prediction guarantee. No betting advice.
        No DB open/write. No adapter calls. No new scoring. No new scoring cohort.
        No production registry import. No deploy. No blended leaderboard. Not production release approval.

        ## List commands

        ```bash
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --list-commands
        ```

        ## List artifacts

        ```bash
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --list-artifacts
        ```

        ## List deltas

        ```bash
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --list-deltas
        ```

        ## Query by recipe

        ```bash
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query all_commands
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query non_pass_commands
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query all_artifacts
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query stale_or_missing_artifacts
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query all_deltas
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query warn_or_fail_deltas
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --query handoff_digest
        ```

        ## Inspect one command

        ```bash
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --show-command P377-CMD-001
        ```

        ## Inspect one artifact

        ```bash
        python3 -m recovered_strategies.biglotto.no_db_regression_archive_query --show-artifact artifacts/P379_biglotto_regression_archive_explorer_index.json
        ```

        ## Safe caveats

        No DB was opened or written; no adapters were called; no new scoring, scoring cohort, shape-only scoring, blocked-target scoring, or blended leaderboard was created; no production registry import, deploy, or external publication was performed.
        P380 does not execute P371-P379 CLI commands. It queries committed archive evidence only.
        P380 does not authorize DB writes, adapter execution, strategy status changes, deploys, force operations,
        betting advice, future prediction claims, or production release approval.

        ## Generated artifacts

        - artifacts/P380_biglotto_regression_archive_query_index.json
- artifacts/P380_biglotto_regression_archive_query_recipes.json
- artifacts/P380_biglotto_regression_archive_query_command_results.csv
- artifacts/P380_biglotto_regression_archive_query_artifact_results.csv
- artifacts/P380_biglotto_regression_archive_query_delta_results.csv
- artifacts/P380_biglotto_regression_archive_query_transcripts.json
- artifacts/P380_biglotto_regression_archive_query_guide.md
- artifacts/P380_biglotto_regression_archive_query_manifest.csv
