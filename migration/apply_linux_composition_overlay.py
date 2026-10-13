"""Explicit Linux font-domain adaptation; original archive is never rewritten."""
import hashlib,json,shutil
from pathlib import Path
SOURCE_SHA='9ad619a09268bc06744b6438667afb6394264713b793b085ae273aac704e163d'
MODULE='hero_engine/procedural_infographics_phase5.py'
def apply(source,destination):
 source=Path(source).resolve();destination=Path(destination).resolve()
 if destination.exists() or destination==source or source in destination.parents:raise PermissionError('NEW_SEPARATE_SHADOW_REQUIRED')
 raw=(source/MODULE).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA:raise PermissionError('COMPOSITION_SOURCE_IDENTITY_CHANGED')
 text=raw.decode()
 anchor='    typo = bible.get("typography", {})\n'
 declaration='    font_family = "Arial" if __import__("os").name == "nt" else "DejaVu Sans"\n    admitted_font = (Path(r"C:\\Windows\\Fonts") / "arialbd.ttf") if __import__("os").name == "nt" else Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")\n'
 old_family='or "Arial" not in typo.get("families", [])'
 old_font='or font.resolve() != (Path(r"C:\\Windows\\Fonts") / "arialbd.ttf").resolve()'
 for a in [anchor,old_family,old_font]:
  if text.count(a)!=1:raise PermissionError('EXACT_COMPOSITION_ANCHOR_REQUIRED')
 text=text.replace(anchor,anchor+declaration).replace(old_family,'or font_family not in typo.get("families", [])').replace(old_font,'or font.resolve() != admitted_font.resolve()')
 shutil.copytree(source,destination,ignore=shutil.ignore_patterns('__pycache__'))
 (destination/MODULE).write_text(text)
 receipt={'policy':'LINUX_COMPOSITION_FONT_DOMAIN_V1','module':MODULE,'original_sha256':SOURCE_SHA,'shadow_sha256':hashlib.sha256(text.encode()).hexdigest(),'original_preserved':True,'requires_explicit_linux_font_family_in_style_bible':True,'palette_safe_area_measurement_and_source_identity_guards_preserved':True,'production_ready':False}
 (destination/'linux-composition-overlay.json').write_text(json.dumps(receipt,indent=2))
 return receipt
