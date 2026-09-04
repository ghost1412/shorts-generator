# Contributing to ShortsFlow AI Studio

First off, thank you for considering contributing to ShortsFlow AI Studio! It's people like you that make open-source such a fantastic community to learn, inspire, and create.

## 🚀 How Can I Contribute?

### 1. Reporting Bugs
If you find a bug, please create an issue! Include:
- A quick summary of the bug
- Steps to reproduce
- What you expected to happen vs what actually happened
- Your OS, Python version, and Node.js version (if applicable)

### 2. Suggesting Enhancements
Have an idea for a new Video Mode, a new Caption Style, or an LLM integration? We'd love to hear it. Create an issue explaining:
- The feature you want
- Why it would be useful
- How it might be implemented

### 3. Submitting Pull Requests (PRs)
1. **Fork the repo** and create your branch from `develop`.
2. **If you've added code** that should be tested, add tests.
3. **If you've changed APIs**, update the documentation.
4. **Ensure the test suite passes** (if applicable).
5. **Issue that PR!**

## 💻 Development Setup
1. Clone your fork and run `setup.bat` to install all dependencies.
2. We recommend testing your changes with the `--preview` flag or a short `--target_duration` to save LLM tokens and render time during testing.

## 🎨 Adding New Caption Styles
If you're adding new styles to `remotion-video/`, please ensure they are responsive to different aspect ratios and clearly documented in `ShortFlow.tsx`.

## 🤖 Adding New LLMs
When adding support for a new LLM provider in `engine/script_gen.py`, please ensure it includes proper fallback logic and respects the `max_tokens` limit required by different prompt modes.
