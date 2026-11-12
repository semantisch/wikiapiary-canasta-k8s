#!/usr/bin/env python3
"""Render a behavioral Varnish test against the actual production VCL."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
vcl = (root / 'charts/canasta/files/default.vcl').read_text()
vcl = vcl.replace('__PRIMARY_HOST__', 'wikiapiary.test')
vcl = re.sub(r'backend default \{.*?\n\}',
             'backend default { .host = "${s1_addr}"; .port = "${s1_port}"; }',
             vcl, count=1, flags=re.S)
print((root / 'scripts/homepage-grace.vtc.in').read_text().replace('__VCL__', vcl))
