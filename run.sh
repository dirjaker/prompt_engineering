#!/bin/bash
cd "$(dirname "$0")"
source activate prompt_engineering 2>/dev/null || conda activate prompt_engineering 2>/dev/null
python api.py
