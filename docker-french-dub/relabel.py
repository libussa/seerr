#!/usr/bin/env python3
"""Apply the personal display-only overlay to a clean upstream source tree."""
import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
label = 'doublage français'
# Restrict replacement to known display surfaces. Never touch scanner logic,
# API field names, permission constants, or database migrations.
source_paths = [
    'server/entity/MediaRequest.ts',
    'server/lib/notifications/agents/email.ts',
    'server/lib/notifications/agents/webpush.ts',
    'server/routes/media.ts',
    'server/subscriber/MediaRequestSubscriber.ts',
    'src/components/CollectionDetails/index.tsx',
    'src/components/Common/StatusBadgeMini/index.tsx',
    'src/components/DownloadBlock/index.tsx',
    'src/components/IssueDetails/index.tsx',
    'src/components/ManageSlideOver/index.tsx',
    'src/components/MovieDetails/index.tsx',
    'src/components/PermissionEdit/index.tsx',
    'src/components/RequestBlock/index.tsx',
    'src/components/RequestButton/index.tsx',
    'src/components/RequestModal/CollectionRequestModal.tsx',
    'src/components/RequestModal/MovieRequestModal.tsx',
    'src/components/RequestModal/TvRequestModal.tsx',
    'src/components/Settings/RadarrModal/index.tsx',
    'src/components/Settings/SettingsServices.tsx',
    'src/components/Settings/SonarrModal/index.tsx',
    'src/components/StatusBadge/index.tsx',
    'src/components/TvDetails/index.tsx',
    'src/i18n/globalMessages.ts',
]


def relabel(text, french=False):
    if french:
        text = re.sub(r'non[- ]4K', 'standard', text, flags=re.I)
        return re.sub(r'\b4K\b', label, text, flags=re.I)
    text = text.replace('non-4K', 'standard')
    text = text.replace('in 4K', f'with {label}')
    return re.sub(r'\b4K\b', label, text)


# Validate all expected locations before writing anything.
changes = {}
for name in source_paths:
    path = root / name
    old = path.read_text()
    new = ''.join(
        line if line.lstrip().startswith('//') else relabel(line)
        for line in old.splitlines(keepends=True)
    )
    if old == new:
        raise SystemExit(f'Upstream changed: no expected labels in {name}')
    changes[path] = new

for directory in ('src/i18n/locale', 'server/i18n/locale'):
    for locale in ('en', 'fr'):
        path = root / directory / f'{locale}.json'
        old = json.loads(path.read_text())
        new = {key: relabel(value, locale == 'fr') for key, value in old.items()}
        if old == new:
            raise SystemExit(f'Upstream changed: no expected labels in {path}')
        changes[path] = json.dumps(new, ensure_ascii=False, indent=2) + '\n'

for path, text in changes.items():
    path.write_text(text)
print(f'Applied {label!r} overlay to {len(changes)} files.')
