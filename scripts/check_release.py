"""Validate the standalone skill and smoke-test its install archive and template."""
import hashlib
import html
import re
import tempfile
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
NAME = 'amazon-listing-catalog-workflow'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(root):
    text = (root / 'SKILL.md').read_text(encoding='utf-8')
    front = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
    require(front is not None, 'SKILL.md needs YAML frontmatter')
    data = yaml.safe_load(front.group(1))
    require(data.get('name') == NAME, 'Unexpected skill name')
    require(isinstance(data.get('description'), str) and 0 < len(data['description']) <= 1024,
            'Description must be a string of 1-1024 characters')
    config = yaml.safe_load((root / 'agents/openai.yaml').read_text(encoding='utf-8'))
    ui = config['interface']
    require(25 <= len(ui['short_description']) <= 64, 'Invalid UI description length')
    require('$' + NAME in ui['default_prompt'], 'Prompt missing skill invocation')
    for doc in [root / 'SKILL.md', *sorted((root / 'references').glob('*.md'))]:
        body = doc.read_text(encoding='utf-8')
        for link in re.findall(r'\]\(([^)]+)\)', body):
            if '://' in link or link.startswith('#'):
                continue
            target = (doc.parent / link.split('#')[0]).resolve()
            require(target.is_relative_to(root.resolve()), f'Link escapes skill: {link}')
            require(target.is_file(), f'Missing resource: {doc.name} -> {link}')
    template = (root / 'assets/listing-staff-entry-shell.html').read_text(encoding='utf-8')
    values = {
        'TITLE': html.escape('安装验证 <示例>'), 'META': '<span>LOCAL TEST</span>',
        'BANNER_CLASS': 'conditional', 'BANNER_TITLE': '内部草稿',
        'BANNER_BODY': '尚未发布', 'CONTENT': '<article><h2>测试正文</h2></article>',
    }
    require(set(re.findall(r'\{\{(\w+)\}\}', template)) == set(values),
            'Template requires unsupported inputs')
    require('receipt-ledger' not in template and 'COORDINATION_RECEIPT' not in template,
            'Internal template depends on missing publish coordinator')
    for key, value in values.items():
        template = template.replace('{{' + key + '}}', value)
    require('{{' not in template, 'Unresolved template placeholder')
    require('测试正文' in template and '&lt;示例&gt;' in template, 'Render smoke test failed')
    require(not re.search(r'<\s*(form|input|button|select|textarea)\b', template, re.I),
            'Read-only template contains submission controls')


def main():
    validate(ROOT)
    files = [ROOT / 'SKILL.md']
    for directory in ['agents', 'references', 'assets']:
        files.extend(sorted(p for p in (ROOT / directory).rglob('*') if p.is_file()))
    require(all(not p.is_symlink() for p in files), 'Symlinks are not portable')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    archive = dist / (NAME + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        for source in files:
            output.write(source, NAME + '/' + source.relative_to(ROOT).as_posix())
    with tempfile.TemporaryDirectory(prefix='skill-install-smoke-') as tmp:
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            require(all(n.startswith(NAME + '/') and '..' not in Path(n).parts for n in names),
                    'Unsafe archive layout')
            require(NAME + '/SKILL.md' in names, 'Missing installation entrypoint')
            bundle.extractall(tmp)
        installed = Path(tmp) / NAME
        validate(installed)
        for source in files:
            require(source.read_bytes() == (installed / source.relative_to(ROOT)).read_bytes(),
                    f'Installed file mismatch: {source.name}')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (dist / 'SHA256SUMS').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(f'PASS: YAML, resource links, template render, ZIP extraction and {len(files)} file comparisons')
    print(f'Archive: {archive}')
    print('Scope: packaging only; not live host activation or consumer-copy quality')


if __name__ == '__main__':
    main()
