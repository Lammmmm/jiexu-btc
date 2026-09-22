"""One-time supply-chain record; not imported by runtime."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen
from backend.config import ROOT

def main():
    archive=ROOT/"data/calendar_source/lunar_python-1.4.8.tar.gz"
    with urlopen("https://pypi.org/pypi/lunar_python/1.4.8/json",timeout=20) as response:
        release=json.load(response)
    published=next(f for f in release["urls"] if f["filename"]==archive.name)
    actual=hashlib.sha256(archive.read_bytes()).hexdigest()
    assert actual==published["digests"]["sha256"],"Source archive checksum mismatch"
    result={"package":"lunar_python","version":"1.4.8","github":"https://github.com/6tail/lunar-python",
            "filename":archive.name,"download_url":published["url"],"sha256":actual,
            "verified_against":"https://pypi.org/pypi/lunar_python/1.4.8/json","license":"MIT"}
    (archive.parent/"source-archive.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
