"""Reject a title from another editorial treatment before native effects."""
import re

def require_alignment(music, visual):
    if music.get('voice_required') is not True:
        return {'status':'NOT_APPLICABLE_INSTRUMENTAL_ONLY','publication_authorized':False}
    editorial=music.get('recipe',{}).get('editorial',{})
    title=editorial.get('title')
    displayed=visual.get('layout',{}).get('title')
    if not isinstance(title,str) or not isinstance(displayed,str):
        raise PermissionError('EDITORIAL_VISUAL_TITLE_MISSING')
    expected=title.split('|',1)[0].strip()
    normalized=lambda value:re.sub(r'\s+',' ',value).strip().casefold()
    if not expected or not normalized(displayed) or normalized(expected)!=normalized(displayed):
        raise PermissionError('EDITORIAL_VISUAL_PROMISE_MISMATCH')
    return {'status':'EXACT_EDITORIAL_VISUAL_TITLE_ALIGNED','expected_title':expected,
            'displayed_title':displayed,'quality_authorized':False,'publication_authorized':False}
