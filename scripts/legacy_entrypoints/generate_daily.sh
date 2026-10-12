#!/bin/bash
d=$(date +"%Y-%m-%d")
mkdir -p data/wbc_backend/reports/Day2/
echo "# WBC Daily Report for $d" > data/wbc_backend/reports/Daily_${d}.md
cat data/wbc_backend/reports/Day1_Summary_V3_Institutional.md >> data/wbc_backend/reports/Daily_${d}.md
echo "Daily report Daily_${d}.md generated successfully."
