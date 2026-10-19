"""Downloads JSON data only, explicitly via this script; never downloads code."""
import json
from pathlib import Path
import sys
import tempfile
import os
import urllib.request

ROOT = 'https://raw.githubusercontent.com/a2x/cs2-dumper/'
FIELD_MAP = {
    'health': ('C_BaseEntity', 'm_iHealth'),
    'team': ('C_BaseEntity', 'm_iTeamNum'),
    'life_state': ('C_BaseEntity', 'm_lifeState'),
    'scene_node': ('C_BaseEntity', 'm_pGameSceneNode'),
    'origin': ('CGameSceneNode', 'm_vecAbsOrigin'),
    'dormant': ('CGameSceneNode', 'm_bDormant'),
    'view_offset': ('C_BasePlayerPawn', 'm_vecViewOffset'),
    'eye_angles': ('C_CSPlayerPawn', 'm_angEyeAngles'),
    'pawn_handle': ('CCSPlayerController', 'm_hPlayerPawn'),
    'name': ('CBasePlayerController', 'm_iszPlayerName'),
}


def get_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'CS2-ESP-Offset-Data'})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(8_000_001)
    if len(raw) > 8_000_000:
        raise ValueError('Antwort zu groß')
    return json.loads(raw)


def extract(offsets, schema, commit):
    classes = schema['client.dll']['classes']

    def field(class_name, name):
        for _ in range(30):
            cls = classes[class_name]
            if name in cls['fields']:
                return cls['fields'][name]
            class_name = cls['parent']
            if not class_name:
                break
        raise ValueError(f'Feld fehlt: {name}')

    result = {'source_commit': commit, 'globals': {}, 'fields': {}}
    for name in ('dwEntityList', 'dwViewMatrix', 'dwLocalPlayerPawn'):
        result['globals'][name] = offsets['client.dll'][name]
    for alias, (class_name, name) in FIELD_MAP.items():
        result['fields'][alias] = field(class_name, name)
    validate(result)
    return result


def validate(data):
    if len(data['source_commit']) != 40 or any(c not in '0123456789abcdef' for c in data['source_commit']):
        raise ValueError('Ungültige Quellversion')
    for name in ('dwEntityList', 'dwViewMatrix', 'dwLocalPlayerPawn'):
        value = data['globals'][name]
        if type(value) is not int or not 0 < value < 0x40000000:
            raise ValueError('Ungültiger globaler Offset')
    for name in FIELD_MAP:
        value = data['fields'][name]
        if type(value) is not int or not 0 <= value < 0x100000:
            raise ValueError('Ungültiger Feld-Offset')


def update(path):
    commit = get_json('https://api.github.com/repos/a2x/cs2-dumper/commits/main')['sha']
    data = extract(get_json(ROOT + commit + '/output/offsets.json'),
                   get_json(ROOT + commit + '/output/client_dll.json'), commit)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.offsets-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return commit


if __name__ == '__main__':
    directory = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    try:
        print('Offsets aktualisiert:', update(directory / 'offsets.json'))
    except Exception as error:
        print('Aktualisierung fehlgeschlagen:', error)
        sys.exit(1)
