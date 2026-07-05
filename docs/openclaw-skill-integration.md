# OpenClaw Skill Integration

This document describes external skill integration concepts for OpenClaw-style workflows.

## Purpose

A skill package should describe reusable capabilities, required inputs, expected outputs, and integration boundaries. Daily Stock Analysis keeps repository collaboration rules in `AGENTS.md`; product or external integration documentation should not override that source of truth.

## Integration Checklist

- Keep skill names and runtime identifiers stable.
- Document required configuration and security boundaries.
- Avoid committing secrets or local-only paths.
- Provide validation steps and rollback guidance.