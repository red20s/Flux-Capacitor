"""Build Kodi ZIPs and the bundled repository using Python 3 standard library."""
from pathlib import Path
import hashlib
import shutil
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
DIST.mkdir(exist_ok=True)
PLUGIN = ROOT / 'plugin.video.reely'
REPO = ROOT / 'repository.reely'

def pack(source, target):
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                archive.write(path, path.relative_to(source.parent).as_posix())

plugin_xml = ET.parse(PLUGIN / 'addon.xml').getroot()
plugin_zip = f"{plugin_xml.attrib['id']}-{plugin_xml.attrib['version']}.zip"
pack(PLUGIN, DIST / plugin_zip)
packages = REPO / 'packages'
folder = packages / plugin_xml.attrib['id']
folder.mkdir(parents=True, exist_ok=True)
shutil.copyfile(DIST / plugin_zip, folder / plugin_zip)
shutil.copyfile(PLUGIN / 'addon.xml', folder / 'addon.xml')
index = b'<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n' + ET.tostring(plugin_xml) + b'\n</addons>\n'
(packages / 'addons.xml').write_bytes(index)
(packages / 'addons.xml.md5').write_text(hashlib.md5(index).hexdigest(), encoding='ascii')
repo_xml = ET.parse(REPO / 'addon.xml').getroot()
repo_zip = f"{repo_xml.attrib['id']}-{repo_xml.attrib['version']}.zip"
pack(REPO, DIST / repo_zip)
print('Built:', plugin_zip, repo_zip)
