import hashlib
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path


class InstallError(Exception):
    pass


class ParulaRelease:
    """The current public Parula release for Linux: the official .deb from GitHub, unpacked without root
    (`dpkg -x`), with its version and SHA-256 recorded next to it."""

    api = "https://api.github.com/repos/mustang-im/mustang/releases/latest"

    def __init__(self, target: Path, progress=print):
        self.target = Path(target)
        self.progress = progress

    def latest(self) -> dict:
        request = urllib.request.Request(self.api, headers={"Accept": "application/vnd.github+json",
                                                            "User-Agent": "parula-speed-benchmark"})
        with urllib.request.urlopen(request, timeout=60) as response:
            release = json.load(response)
        if release.get("prerelease") or release.get("draft"):
            raise InstallError(f"The latest release {release.get('tag_name')} is not a public release")
        asset = next((a for a in release.get("assets", [])
                      if a["name"].startswith("parula_") and a["name"].endswith("_amd64.deb")), None)
        if asset is None:
            raise InstallError(f"Release {release.get('tag_name')} has no parula_*_amd64.deb")
        return {"tag": release["tag_name"], "published": release.get("published_at"), "name": asset["name"],
                "url": asset["browser_download_url"], "size": asset["size"]}

    def install(self) -> dict:
        release = self.latest()
        info_path = self.target / "release.json"
        if info_path.exists() and json.loads(info_path.read_text()).get("name") == release["name"]:
            self.progress(f"{release['name']} is already unpacked in {self.target}")
            return json.loads(info_path.read_text())
        self.target.mkdir(parents=True, exist_ok=True)
        deb = self.target / release["name"]
        self.progress(f"downloading {release['url']}")
        digest = hashlib.sha256()
        with urllib.request.urlopen(release["url"], timeout=600) as response, open(deb, "wb") as out:
            while chunk := response.read(1 << 20):
                digest.update(chunk)
                out.write(chunk)
        if deb.stat().st_size != release["size"]:
            raise InstallError(f"{deb.name}: {deb.stat().st_size} bytes, the release lists {release['size']}")
        root = self.target / "root"
        if root.exists():
            shutil.rmtree(root)
        subprocess.run(["dpkg", "-x", str(deb), str(root)], check=True)
        release["sha256"] = digest.hexdigest()
        release["binary"] = str(root / "opt" / "Parula" / "parula")
        info_path.write_text(json.dumps(release, indent=2))
        self.progress(f"unpacked {release['name']} ({release['tag']}, sha256 {release['sha256']}) into {root}")
        return release
