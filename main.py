"""Repo entry point, kept so `python main.py ...` (docs, workflows, subprocess callers) keeps working.
The pipeline lives in shortsflow/_main.py; `pip install shortsflow` exposes it as the `shortsflow` command."""
import runpy

runpy.run_module("shortsflow._main", run_name="__main__")
