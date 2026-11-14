"""Bundled illustrations. User-uploaded covers always take precedence."""
SHOWCASE_COVERS = ('campus', 'city', 'learn', 'green', 'finance', 'winter', 'access')

def cover_for(hackathon):
    if hackathon.cover:
        return hackathon.cover
    key = hackathon.demo_key or ''
    if key.startswith('showcase-'):
        try:
            index = int(key.removeprefix('showcase-'))
        except ValueError:
            index = -1
        if 0 <= index < len(SHOWCASE_COVERS):
            return '/hackathons/' + SHOWCASE_COVERS[index] + '.svg'
    return '/hackathons/default.svg'
