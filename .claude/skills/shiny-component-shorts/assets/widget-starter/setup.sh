#!/usr/bin/env bash
set -euo pipefail
uv add \
  shiny \
  shinywidgets \
  plotly
uv run shiny run app.py
