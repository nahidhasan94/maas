import hashlib
from hashlib import sha256
from pathlib import Path

from django.db import connection
import pytest

from maasserver.bootresources import export_images_from_db
from maasserver.enum import BOOT_RESOURCE_FILE_TYPE, BOOT_RESOURCE_TYPE
from maasserver.fields import LargeObjectFile
from maasserver.models.bootresourcefile import BootResourceFile
from maasserver.models.bootresourceset import BootResourceSet
from maasserver.models.largefile import LargeFile
from maasserver.utils.orm import reload_object


@pytest.fixture
def target_dir(tmpdir):
    yield Path(tmpdir / "images-export")


def list_files(base_path):
    return {str(path.relative_to(base_path)) for path in base_path.iterdir()}


@pytest.mark.usefixtures("maasdb")
class TestExportImagesFromDB:
    def make_LargeFile(self, factory, content: bytes = None, size=None):
        if content is None:
            content_size = size
            if content_size is None:
                content_size = 512
            content = factory.make_bytes(size=content_size)
        if size is None:
            size = len(content)
        sha256 = hashlib.sha256()
        sha256.update(content)
        digest = sha256.hexdigest()
        largeobject = LargeObjectFile()
        with largeobject.open("wb") as stream:
            stream.write(content)
        return LargeFile.objects.create(
            sha256=digest,
            size=len(content),
            total_size=size,
            content=largeobject,
        )

    def make_boot_resource_file_with_content_largefile(
        self,
        factory,
        resource_set: BootResourceSet,
        filename: str | None = None,
        filetype: str | None = None,
        extra: str | None = None,
        content: bytes | None = None,
        size: int | None = None,
    ) -> BootResourceFile:
        largefile = self.make_LargeFile(factory, content=content, size=size)
        return factory.make_BootResourceFile(
            resource_set,
            filename=filename,
            filetype=filetype,
            size=largefile.size,
            sha256=largefile.sha256,
            extra=extra,
            largefile=largefile,
        )

    def test_empty(self, target_dir):
        export_images_from_db(target_dir)
        assert list_files(target_dir) == {"bootloaders"}

    def test_create_files(self, target_dir, factory):
        resource1 = factory.make_BootResource(
            name="ubuntu/jammy",
            architecture="s390x/generic",
        )
        resource_set1 = factory.make_BootResourceSet(
            resource=resource1,
            version="20230901",
            label="stable",
        )
        content1 = b"ubuntu-jammy"
        self.make_boot_resource_file_with_content_largefile(
            factory,
            resource_set=resource_set1,
            filename="boot-initrd",
            content=content1,
        )

        resource2 = factory.make_BootResource(
            name="centos/8",
            architecture="amd64/generic",
        )
        resource_set2 = factory.make_BootResourceSet(
            resource=resource2,
            version="20230830",
            label="candidate",
        )
        content2 = b"centos-8"
        self.make_boot_resource_file_with_content_largefile(
            factory,
            resource_set=resource_set2,
            filename="boot-kernel",
            content=content2,
        )
        export_images_from_db(target_dir)
        assert list_files(target_dir) == {
            "bootloaders",
            sha256(content1).hexdigest(),
            sha256(content2).hexdigest(),
        }

    def test_remove_extra_files(self, target_dir, factory):
        target_dir.mkdir()
        extra_file = target_dir / "abcde"
        extra_file.write_text("some content")

        export_images_from_db(target_dir)
        assert not extra_file.exists()

    def test_export_overwrite_changed(self, target_dir, factory):
        target_dir.mkdir()

        content = b"ubuntu-jammy"
        image = target_dir / sha256(content).hexdigest()
        image.write_bytes(b"old")

        resource = factory.make_BootResource(
            name="ubuntu/jammy",
            architecture="s390x/generic",
        )
        resource_set = factory.make_BootResourceSet(
            resource=resource,
            version="20230901",
            label="stable",
        )
        self.make_boot_resource_file_with_content_largefile(
            factory,
            resource_set=resource_set,
            filename="boot-initrd",
            content=content,
        )
        export_images_from_db(target_dir)
        assert image.read_bytes() == content

    def test_remove_largfile(self, target_dir, factory):
        resource = factory.make_BootResource(
            name="ubuntu/jammy",
            architecture="s390x/generic",
        )
        resource_set = factory.make_BootResourceSet(
            resource=resource,
            version="20230901",
            label="stable",
        )
        resource_file = self.make_boot_resource_file_with_content_largefile(
            factory,
            resource_set=resource_set,
            filename="boot-initrd",
            content=b"some content",
        )
        largefile = resource_file.largefile
        export_images_from_db(target_dir)

        assert reload_object(largefile) is None
        # largeobject also gets deleted
        with connection.cursor() as cursor:
            cursor.execute("SELECT loid FROM pg_largeobject")
            assert cursor.fetchall() == []

    def test_no_largefile_ignore(self, target_dir, factory):
        resource = factory.make_BootResource(
            name="ubuntu/jammy",
            architecture="s390x/generic",
        )
        resource_set = factory.make_BootResourceSet(
            resource=resource,
            version="20230901",
            label="stable",
        )
        sha256 = "abcde"
        factory.make_BootResourceFile(
            resource_set=resource_set,
            largefile=None,
            filename="boot-initrd",
            sha256=sha256,
            size=100,
        )

        target_dir.mkdir()
        resource_file = target_dir / sha256
        resource_file.touch()
        export_images_from_db(target_dir)
        assert resource_file.exists()

    def test_booloaders_export(self, tmpdir, target_dir, factory):
        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name="grub-efi/uefi",
            architecture="amd64/generic",
            bootloader_type="uefi",
        )
        resource_set = factory.make_BootResourceSet(
            resource=resource,
            version="20230901",
            label="stable",
        )
        tarball = Path(
            factory.make_tarball(
                tmpdir,
                {
                    "grubx64.efi": b"grub content",
                    "bootx64.efi": b"boot content",
                },
            )
        )
        self.make_boot_resource_file_with_content_largefile(
            factory,
            resource_set=resource_set,
            filetype=BOOT_RESOURCE_FILE_TYPE.ARCHIVE_TAR_XZ,
            filename="grub2-signed.tar.xz",
            content=tarball.read_bytes(),
        )
        export_images_from_db(target_dir)
        bootloader_dir = target_dir / "bootloaders/uefi/amd64"
        assert list_files(bootloader_dir) == {
            "grubx64.efi",
            "bootx64.efi",
        }
