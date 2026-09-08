"""Scan a Jenkinsfile and produce a GitHub Actions migration checklist."""

from migration_analyzer.analyzer import analyze, analyze_text
from migration_analyzer.model import Category, Finding, Report

__all__ = ["Category", "Finding", "Report", "analyze", "analyze_text"]
__version__ = "0.1.0"
