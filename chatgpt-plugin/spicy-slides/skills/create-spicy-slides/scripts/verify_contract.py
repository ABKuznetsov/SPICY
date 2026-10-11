"""Check the shipped generation SDK before writing a presentation."""
import hashlib
import json
from pathlib import Path

FILES=('assets/schema.json','assets/starter.json','scripts/strict_contract.py','scripts/package_spicy.py','scripts/author_spicy.py','scripts/widget_contract.py','scripts/verify_contract.py','scripts/create_widget.py','scripts/package_widget_plugin.py')
def verify():
    base=Path(__file__).parent.parent
    lock=json.loads((base/'assets/contract-lock.json').read_text())
    if lock.get('profile')!='spicy-gpt-authoring-v1' or lock.get('formatVersion')!='1.0.0' or set(lock.get('files',{}))!=set(FILES):
        raise ValueError('Generation contract identity mismatch; restore the original plugin SDK')
    for path in FILES:
        if hashlib.sha256((base/path).read_bytes()).hexdigest()!=lock['files'][path]:
            raise ValueError('Generation SDK was modified: '+path+'; restore it instead of changing the format')
    return lock
if __name__=='__main__':print(json.dumps({'verified':True,'profile':verify()['profile']}))
