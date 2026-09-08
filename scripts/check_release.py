"""Validate three companion skills, then build and verify their release archives."""
import hashlib
import html
import re
import tempfile
import zipfile
from pathlib import Path

import yaml
from check_package import NAMES, verify

ROOT = Path(__file__).resolve().parents[1]
NAME = 'amazon-listing-catalog-workflow'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(root, name=NAME):
    text = (root / 'SKILL.md').read_text(encoding='utf-8')
    front = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
    require(front is not None, 'SKILL.md needs YAML frontmatter')
    data = yaml.safe_load(front.group(1))
    require(data.get('name') == name, 'Unexpected skill name')
    require(isinstance(data.get('description'), str) and 0 < len(data['description']) <= 1024,
            'Description must be a string of 1-1024 characters')
    config = yaml.safe_load((root / 'agents/openai.yaml').read_text(encoding='utf-8'))
    ui = config['interface']
    require(25 <= len(ui['short_description']) <= 64, 'Invalid UI description length')
    require('$' + name in ui['default_prompt'], 'Prompt missing skill invocation')
    for doc in [root / 'SKILL.md', *sorted((root / 'references').glob('*.md'))]:
        body = doc.read_text(encoding='utf-8')
        for link in re.findall(r'\]\(([^)]+)\)', body):
            if '://' in link or link.startswith('#'):
                continue
            target = (doc.parent / link.split('#')[0]).resolve()
            require(target.is_relative_to(root.resolve()), f'Link escapes skill: {link}')
            require(target.is_file(), f'Missing resource: {doc.name} -> {link}')
    if name != NAME:
        return
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
    skill_root = ROOT / 'skills'
    errors = verify(skill_root)
    require(not errors, '\n'.join(errors))
    for name in NAMES:
        validate(skill_root / name, name)
    files = sorted(p for p in skill_root.rglob('*')
                   if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    require(all(not p.is_symlink() for p in files), 'Symlinks are not portable')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    checksums = []
    for archive_name, selected in [('amazon-skills-complete', NAMES), *[(n, (n,)) for n in NAMES]]:
        archive = dist / (archive_name + '.zip')
        sources = [p for p in files if p.relative_to(skill_root).parts[0] in selected]
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
            for source in sources:
                output.write(source, source.relative_to(skill_root).as_posix())
        with tempfile.TemporaryDirectory(prefix='skill-install-smoke-') as tmp:
            with zipfile.ZipFile(archive) as bundle:
                require(all(Path(n).parts[0] in selected and '..' not in Path(n).parts
                            for n in bundle.namelist()), 'Unsafe archive layout')
                bundle.extractall(tmp)
            installed = Path(tmp)
            for name in selected:
                validate(installed / name, name)
            if len(selected) == len(NAMES):
                require(not verify(installed), 'Incomplete full-suite ZIP')
            for source in sources:
                require(source.read_bytes() == (installed / source.relative_to(skill_root)).read_bytes(),
                        f'Installed file mismatch: {source.name}')
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        checksums.append(f'{digest}  {archive.name}\n')
        print(f'Archive verified: {archive.name} ({len(sources)} files)')
    (dist / 'SHA256SUMS').write_text(''.join(checksums), encoding='utf-8')
    print(f'PASS: 3 skills, YAML, resource links, template render, ZIP extraction and {len(files)} files')
    print('Scope: packaging only; not live host activation or consumer-copy quality')


if __name__ == '__main__':
    main()
