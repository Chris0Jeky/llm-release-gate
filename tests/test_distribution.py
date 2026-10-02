"""Release acceptance rejects metadata that can add runtime dependencies."""

import io
import tarfile
import zipfile

import pytest

from scripts.verify_dist import NOTICES, PROJECT, project_version, verify_archives


@pytest.mark.parametrize("requirement,valid", [
    ('pytest>=8; extra == "dev"', True),
    ("unexpected-runtime", False),
    ('unexpected-runtime; extra == "dev" or python_version >= "3.11"', False),
])
def test_archive_dependencies_must_be_declared_optional_only(tmp_path, requirement, valid):
    version = project_version()
    root = f"llm_release_gate-{version}"
    with tarfile.open(tmp_path / f"{root}.tar.gz", "w:gz") as archive:
        for notice in NOTICES:
            content = (PROJECT / notice).read_bytes()
            member = tarfile.TarInfo(f"{root}/{notice}")
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    metadata = "\n".join([
        "Metadata-Version: 2.1", f"Version: {version}", "License: GPL-3.0-only",
        *(f"License-File: {notice}" for notice in NOTICES),
        f"Requires-Dist: {requirement}", "",
    ])
    with zipfile.ZipFile(tmp_path / f"{root}-py3-none-any.whl", "w") as archive:
        archive.writestr(f"{root}.dist-info/METADATA", metadata)
        for notice in NOTICES:
            archive.writestr(f"{root}.dist-info/licenses/{notice}", (PROJECT / notice).read_bytes())
    if valid:
        verify_archives(tmp_path)
    else:
        with pytest.raises(AssertionError, match="dependenc"):
            verify_archives(tmp_path)
