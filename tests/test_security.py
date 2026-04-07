"""Tests for mcpforge AST security scanner."""

from mcpforge.security import check_security


class TestCheckSecurity:
    def test_clean_fastmcp_code_no_findings(self):
        code = '''
import uuid
from datetime import datetime, timezone
from fastmcp import FastMCP

mcp = FastMCP("Todo")

@mcp.tool
async def create_todo(title: str) -> dict:
    return {"id": str(uuid.uuid4()), "title": title}
'''
        assert check_security(code) == []

    def test_detects_eval(self):
        code = 'result = eval("1+1")\n'
        findings = check_security(code)
        assert len(findings) == 1
        assert "DANGEROUS" in findings[0]
        assert "eval" in findings[0]

    def test_detects_exec(self):
        code = 'exec("import os")\n'
        findings = check_security(code)
        assert any("exec" in f for f in findings)
        assert any("DANGEROUS" in f for f in findings)

    def test_detects_os_system(self):
        code = 'import os\nos.system("ls")\n'
        findings = check_security(code)
        dangerous = [f for f in findings if "DANGEROUS" in f]
        assert len(dangerous) == 1
        assert "os.system" in dangerous[0]

    def test_detects_subprocess_run(self):
        code = 'import subprocess\nsubprocess.run(["ls"])\n'
        findings = check_security(code)
        dangerous = [f for f in findings if "DANGEROUS" in f]
        assert len(dangerous) == 1
        assert "subprocess.run" in dangerous[0]

    def test_detects_subprocess_popen(self):
        code = 'import subprocess\nsubprocess.Popen(["ls"])\n'
        findings = check_security(code)
        assert any("subprocess.Popen" in f for f in findings)

    def test_detects_shutil_rmtree(self):
        code = 'import shutil\nshutil.rmtree("/")\n'
        findings = check_security(code)
        assert any("shutil.rmtree" in f for f in findings)

    def test_flags_unknown_import(self):
        code = 'import boto3\n'
        findings = check_security(code)
        assert len(findings) == 1
        assert "WARNING" in findings[0]
        assert "boto3" in findings[0]

    def test_allows_all_whitelisted_imports(self):
        code = '''
import json
import logging
import asyncio
import pathlib
import uuid
import os
import re
import hashlib
from datetime import datetime
from typing import Any
from fastmcp import FastMCP
from pydantic import BaseModel
import httpx
'''
        findings = check_security(code)
        assert findings == []

    def test_multiple_issues_all_reported(self):
        code = '''
import boto3
import subprocess
eval("1+1")
subprocess.run(["ls"])
os.system("whoami")
'''
        findings = check_security(code)
        assert len(findings) >= 4  # 1 unknown import + eval + subprocess.run + os.system

    def test_detects_compile(self):
        code = 'compile("pass", "<string>", "exec")\n'
        findings = check_security(code)
        assert any("compile" in f for f in findings)

    def test_detects_dunder_import(self):
        code = '__import__("os")\n'
        findings = check_security(code)
        assert any("__import__" in f for f in findings)

    def test_syntax_error_returns_empty(self):
        code = "def foo(\n"  # Broken syntax
        assert check_security(code) == []

    def test_unknown_import_is_warning_not_dangerous(self):
        code = "import boto3\n"
        findings = check_security(code)
        assert all("WARNING" in f for f in findings)
        assert not any("DANGEROUS" in f for f in findings)

    def test_import_from_unknown_module(self):
        code = "from celery import Celery\n"
        findings = check_security(code)
        assert len(findings) == 1
        assert "WARNING" in findings[0]
        assert "celery" in findings[0]
