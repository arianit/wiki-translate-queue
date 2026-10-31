#!/usr/bin/env python3
"""Validate KEK Wikitext and saved live MediaWiki evidence; optional read-only URL audit.

Run from the article directory: python3 tools/validate_kek.py [--network]
The network option fetches citation URLs; it does not edit Wikimedia or any website.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'research' / 'data'


class ErrorElements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errors = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get('class', '').split())
        if classes & {'error', 'mw-ext-cite-error', 'cs1-visible-error', 'cs1-hidden-error'}:
            self.errors.append({'tag': tag, 'attributes': attrs})


def local_checks():
    text = (ROOT / 'KEK.sq.wiki').read_text()
    failures = []
    definitions = re.findall(r'<ref\s+name="([^"]+)"\s*>(.*?)</ref>', text, re.S)
    reused = re.findall(r'<ref\s+name="([^"]+)"\s*/>', text)
    counts = Counter(name for name, _ in definitions)
    if any(n > 1 for n in counts.values()):
        failures.append('Duplicate named reference definitions')
    if set(reused) - set(counts):
        failures.append('Undefined named references: ' + str(set(reused) - set(counts)))
    if len(re.findall(r'<ref\b[^>]*(?<!/)>', text)) != text.count('</ref>'):
        failures.append('Unbalanced ref tags')
    if text.count('{{') != text.count('}}') or text.count('[[') != text.count(']]'):
        failures.append('Unbalanced templates or wikilinks')
    headings = re.findall(r'^(={2,6})\s*(.*?)\s*\1\s*$', text, re.M)
    if len(headings) != len(set(name for _, name in headings)):
        failures.append('Duplicate headings')
    levels = [len(eq) for eq, _ in headings]
    if any(b > a + 1 for a, b in zip(levels, levels[1:])):
        failures.append('Skipped heading level')
    tables = re.findall(r'^\{\|.*?^\|\}', text, re.S | re.M)
    if len(tables) != len(re.findall(r'^\{\|', text, re.M)):
        failures.append('Unclosed table')
    widths = []
    for table in tables:
        width = next(len(line.split('!!')) for line in table.splitlines() if line.startswith('!'))
        rows = [line for line in table.splitlines() if re.match(r'^\|\s*\w', line)]
        if any(len(row.split('||')) != width for row in rows):
            failures.append('Inconsistent table column count')
        widths.append({'columns': width, 'rows': len(rows)})
    if re.search(r'utm_|fbclid|gclid|TODO|FIXME|```', text, re.I):
        failures.append('Tracking parameter, TODO or Markdown code fence')
    if re.search(r'\d\.\d\s*(?:MW|GWh|TWh|milion)', text):
        failures.append('Decimal point in Albanian numerical prose')
    catalog = json.loads((DATA / 'source-catalog.json').read_text())
    if set(catalog) != set(counts):
        failures.append('Reference catalog differs from article definitions')
    citation_urls = []
    for name, body in definitions:
        for field in ('title', 'url', 'publisher'):
            if not re.search(r'\|' + field + r'\s*=\s*[^|}]+', body):
                failures.append(f'{name}: missing {field}')
        match = re.search(r'\|url=([^|}]+)', body)
        if match:
            url = match.group(1).strip()
            citation_urls.append(url)
            if url != catalog[name]['url']:
                failures.append(name + ': catalog URL mismatch')
    if len(citation_urls) != len(set(citation_urls)):
        failures.append('Duplicate citation URLs under separate named references')
    stripped = re.sub(r'<ref\b.*?</ref>|<ref\b[^>]+/>|\{\{.*?\}\}|\[https?://[^\]]+\]', '', text, flags=re.S)
    if re.search(r'https?://', stripped):
        failures.append('Bare URL in prose')
    uncited = []
    for n, para in enumerate(text.split('\n\n'), 1):
        if not para.startswith(('{{', '==', '{|', '*', '[[Kategoria:')) and re.search(r'\d', para) and '<ref' not in para:
            uncited.append(n)
    if uncited:
        failures.append('Numerical prose paragraphs needing manual review: ' + str(uncited))
    operations = list(csv.DictReader((DATA / 'operations.csv').open()))
    for row in operations:
        a, b, total = (float(row[k]) for k in ('Kosova_A_threshold_GWh', 'Kosova_B_threshold_GWh', 'total_threshold_GWh'))
        if abs(a + b - total) > 0.001:
            failures.append('Generation total mismatch: ' + row['year'])
    template_data = json.loads((DATA / 'templates.json').read_text())
    template_source = next(p['revisions'][0]['slots']['main']['*'] for p in template_data['query']['pages'].values() if p['title'] == 'Stampa:Infobox company')
    fields = re.findall(r'^\|\s*(\w+)\s*=', text.split('}}', 1)[0], re.M)
    for field in fields:
        if '{{{' + field not in template_source:
            failures.append('Unknown infobox field: ' + field)
    rendered = json.loads((DATA / 'wiki-render.json').read_text())
    parsed = rendered.get('parse', {})
    html = parsed.get('text', {}).get('*', '')
    parser = ErrorElements()
    parser.feed(html)
    if parser.errors or parsed.get('parsewarnings') or not parsed:
        failures.append('Live MediaWiki parser or citation errors')
    if 'ib-company' not in html or len(re.findall(r'<table\b[^>]*class="wikitable', html)) != 3:
        failures.append('Missing rendered infobox/table')
    # These are authored links, rather than links generated by template labels.
    targets = sorted(set(re.findall(r'\[\[([^|\]]+)', text)))
    live = {p['title']: p for p in json.loads((DATA / 'wiki-final-titles.json').read_text())['query']['pages'].values()}
    normalized = {p['from']: p['to'] for p in json.loads((DATA / 'wiki-final-titles.json').read_text())['query'].get('normalized', [])}
    missing = [target for target in targets if not target.startswith(('Skeda:', 'File:')) and 'missing' in live.get(normalized.get(target, target), {'missing': ''})]
    if missing:
        failures.append('Missing authored sqwiki targets: ' + str(missing))
    image_pages = json.loads((DATA / 'commons-final.json').read_text())['query']['pages'].values()
    if any('missing' in page or (page['title'].startswith('File:') and not page.get('imageinfo')) for page in image_pages):
        failures.append('Missing Commons photograph or metadata')
    return {'article_sha256': hashlib.sha256(text.encode()).hexdigest(), 'named_references': len(definitions),
            'reference_uses': len(definitions) + len(reused), 'distinct_citation_urls': len(set(citation_urls)),
            'tables': widths, 'headings': len(headings), 'authored_link_targets': targets,
            'live_parse_warnings': parsed.get('parsewarnings', []), 'live_error_elements': parser.errors,
            'failures': failures, 'result': 'PASS' if not failures else 'FAIL'}


def network_audit():
    import requests
    catalog = json.loads((DATA / 'source-catalog.json').read_text())
    items = [(name, item['url']) for name, item in catalog.items()]
    items += [('OfficialWebsite', 'http://kek-energy.com/kek/'), ('EROHomepage', 'https://www.ero-ks.org/')]

    def get(item):
        key, url = item
        row = {'reference': key, 'url': url}
        try:
            try:
                response = requests.get(url, stream=True, timeout=(10, 20), headers={'User-Agent': 'KEKArticleAudit/1.0 (Wikipedia source verification)'})
            except requests.exceptions.SSLError:
                if key != 'KOSTT2013':
                    raise
                row['tls_note'] = 'KOSTT certificate chain could not be validated; public PDF fetched without TLS verification.'
                response = requests.get(url, stream=True, timeout=(10, 20), verify=False)
            with response:
                prefix = next(response.iter_content(8192), b'')
                row.update(status=response.status_code, final_url=response.url, content_type=response.headers.get('Content-Type'), pdf_magic=prefix.startswith(b'%PDF'))
        except requests.RequestException as e:
            row['error'] = str(e)
        return row
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(get, items))
    (DATA / 'url-audit.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'URLs': len(rows), 'status_counts': dict(Counter(str(r.get('status', 'error')) for r in rows))}))


if __name__ == '__main__':
    args = argparse.ArgumentParser()
    args.add_argument('--network', action='store_true')
    opt = args.parse_args()
    if opt.network:
        network_audit()
    else:
        result = local_checks()
        (DATA / 'checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(bool(result['failures']))
