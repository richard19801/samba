# Unix SMB/CIFS implementation.
# Copyright (C) Andrew Bartlett 2012
#
# based on time.py:
# Copyright (C) Sean Dague <sdague@linux.vnet.ibm.com> 2011
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import samba
from samba.tests.samba_tool.base import SambaToolCmdTest
import shutil


def has_difference(path1, path2, binary=True, xml=True, sortlines=False):
    """Use this function to determine if the GPO backup differs from another.

    xml=True checks whether any xml files are equal
    binary=True checks whether any .SAMBABACKUP files are equal
    """
    if os.path.isfile(path1):
        if sortlines:
            file1 = open(path1).readlines()
            file1.sort()
            file2 = open(path1).readlines()
            file2.sort()
            if file1 != file2:
                return path1

        elif open(path1).read() != open(path2).read():
            return path1

        return None

    l_dirs = [ path1 ]
    r_dirs = [ path2 ]
    while l_dirs:
        l_dir = l_dirs.pop()
        r_dir = r_dirs.pop()

        dirlist = os.listdir(l_dir)
        dirlist_other = os.listdir(r_dir)

        dirlist.sort()
        dirlist_other.sort()
        if dirlist != dirlist_other:
            return dirlist

        for e in dirlist:
            l_name = os.path.join(l_dir, e)
            r_name = os.path.join(r_dir, e)

            if os.path.isdir(l_name):
                l_dirs.append(l_name)
                r_dirs.append(r_name)
            else:
                if (l_name.endswith('.xml') and xml or
                    l_name.endswith('.SAMBABACKUP') and binary):
                    if open(l_name).read() != open(r_name).read():
                        return l_name

    return None


class GpoCmdTestCase(SambaToolCmdTest):
    """Tests for samba-tool time subcommands"""

    gpo_name = "testgpo"

    # This exists in the source tree to be restored
    backup_gpo_guid = "{1E1DC8EA-390C-4800-B327-98B56A0AEA5D}"

    def test_gpo_list(self):
        """Run gpo list against the server and make sure it looks accurate"""
        (result, out, err) = self.runsubcmd("gpo", "listall", "-H", "ldap://%s" % os.environ["SERVER"])
        self.assertCmdSuccess(result, out, err, "Ensuring gpo listall ran successfully")

    def test_fetchfail(self):
        """Run against a non-existent GPO, and make sure it fails (this hard-coded UUID is very unlikely to exist"""
        (result, out, err) = self.runsubcmd("gpo", "fetch", "c25cac17-a02a-4151-835d-fae17446ee43", "-H", "ldap://%s" % os.environ["SERVER"])
        self.assertCmdFail(result, "check for result code")

    def test_fetch(self):
        """Run against a real GPO, and make sure it passes"""
        (result, out, err) = self.runsubcmd("gpo", "fetch", self.gpo_guid, "-H", "ldap://%s" % os.environ["SERVER"], "--tmpdir", self.tempdir)
        self.assertCmdSuccess(result, out, err, "Ensuring gpo fetched successfully")
        shutil.rmtree(os.path.join(self.tempdir, "policy"))

    def test_show(self):
        """Show a real GPO, and make sure it passes"""
        (result, out, err) = self.runsubcmd("gpo", "show", self.gpo_guid, "-H", "ldap://%s" % os.environ["SERVER"])
        self.assertCmdSuccess(result, out, err, "Ensuring gpo fetched successfully")

    def test_show_as_admin(self):
        """Show a real GPO, and make sure it passes"""
        (result, out, err) = self.runsubcmd("gpo", "show", self.gpo_guid, "-H", "ldap://%s" % os.environ["SERVER"], "-U%s%%%s" % (os.environ["USERNAME"], os.environ["PASSWORD"]))
        self.assertCmdSuccess(result, out, err, "Ensuring gpo fetched successfully")

    def test_aclcheck(self):
        """Check all the GPOs on the remote server have correct ACLs"""
        (result, out, err) = self.runsubcmd("gpo", "aclcheck", "-H", "ldap://%s" % os.environ["SERVER"], "-U%s%%%s" % (os.environ["USERNAME"], os.environ["PASSWORD"]))
        self.assertCmdSuccess(result, out, err, "Ensuring gpo checked successfully")

    def test_backup_restore_compare_binary(self):
        """Restore from a static backup and compare the binary contents"""

        static_path = os.path.join(self.backup_path, 'policy',
                                   self.backup_gpo_guid)

        temp_path = os.path.join(self.tempdir, 'temp')
        os.mkdir(temp_path)

        new_path = os.path.join(self.tempdir, 'new')
        os.mkdir(new_path)

        gpo_guid = None
        try:
            (result, out, err) = self.runsubcmd("gpo", "restore", "BACKUP_RESTORE1",
                                                static_path,
                                                "-H", "ldap://%s" %
                                                os.environ["SERVER"], "--tmpdir",
                                                temp_path, "--entities",
                                                self.entity_file, "-U%s%%%s" %
                                                (os.environ["USERNAME"],
                                                 os.environ["PASSWORD"]))

            gpo_guid = "{%s}" % out.split("{")[1].split("}")[0]

            (result, out, err) = self.runsubcmd("gpo", "backup", gpo_guid,
                                                "-H", "ldap://%s" %
                                                os.environ["SERVER"],
                                                "--tmpdir", new_path)

            self.assertCmdSuccess(result, out, err, "Ensuring gpo fetched successfully")

            # Compare the directories
            self.assertIsNone(has_difference(os.path.join(new_path, 'policy',
                                                         gpo_guid),
                                            static_path, binary=True,
                                            xml=False))
        finally:
            if gpo_guid:
                (result, out, err) = self.runsubcmd("gpo", "del", gpo_guid,
                                                    "-H", "ldap://%s" %
                                                    os.environ["SERVER"],
                                                    "-U%s%%%s" %
                                                    (os.environ["USERNAME"],
                                                     os.environ["PASSWORD"]))
                self.assertCmdSuccess(result, out, err, "Ensuring gpo deleted successfully")

            shutil.rmtree(temp_path)
            shutil.rmtree(new_path)

    def test_backup_restore_no_entities_compare_binary(self):
        """Restore from a static backup (and use no entity file, resulting in
        copy-restore fallback), and compare the binary contents"""

        static_path = os.path.join(self.backup_path, 'policy',
                                   self.backup_gpo_guid)

        temp_path = os.path.join(self.tempdir, 'temp')
        os.mkdir(temp_path)

        new_path = os.path.join(self.tempdir, 'new')
        os.mkdir(new_path)

        gpo_guid = None
        gpo_guid1 = None
        gpo_guid2 = None
        try:
            (result, out, err) = self.runsubcmd("gpo", "restore", "BACKUP_RESTORE1",
                                                static_path,
                                                "-H", "ldap://%s" %
                                                os.environ["SERVER"], "--tmpdir",
                                                temp_path, "--entities",
                                                self.entity_file, "-U%s%%%s" %
                                                (os.environ["USERNAME"],
                                                 os.environ["PASSWORD"]))

            gpo_guid = "{%s}" % out.split("{")[1].split("}")[0]
            gpo_guid1 = gpo_guid

            # Do not output entities file
            (result, out, err) = self.runsubcmd("gpo", "backup", gpo_guid,
                                                "-H", "ldap://%s" %
                                                os.environ["SERVER"],
                                                "--tmpdir", new_path,
                                                "--generalize")

            self.assertCmdSuccess(result, out, err, "Ensuring gpo fetched successfully")

            # Do not use an entities file
            (result, out, err) = self.runsubcmd("gpo", "restore", "BACKUP_RESTORE2",
                                                os.path.join(new_path, 'policy', gpo_guid1),
                                                "-H", "ldap://%s" %
                                                os.environ["SERVER"], "--tmpdir",
                                                temp_path, "-U%s%%%s" %
                                                (os.environ["USERNAME"],
                                                 os.environ["PASSWORD"]))

            gpo_guid = "{%s}" % out.split("{")[1].split("}")[0]
            gpo_guid2 = gpo_guid

            self.assertCmdSuccess(result, out, err, "Ensuring gpo restored successfully")

            (result, out, err) = self.runsubcmd("gpo", "backup", gpo_guid,
                                                "-H", "ldap://%s" %
                                                os.environ["SERVER"],
                                                "--tmpdir", new_path)

            # Compare the directories
            self.assertIsNone(has_difference(os.path.join(new_path, 'policy',
                                                         gpo_guid1),
                                            os.path.join(new_path, 'policy',
                                                         gpo_guid2),
                                            binary=True, xml=False))
        finally:
            if gpo_guid1:
                (result, out, err) = self.runsubcmd("gpo", "del", gpo_guid1,
                                                    "-H", "ldap://%s" %
                                                    os.environ["SERVER"],
                                                    "-U%s%%%s" %
                                                    (os.environ["USERNAME"],
                                                     os.environ["PASSWORD"]))
                self.assertCmdSuccess(result, out, err, "Ensuring gpo deleted successfully")

            if gpo_guid2:
                (result, out, err) = self.runsubcmd("gpo", "del", gpo_guid2,
                                                    "-H", "ldap://%s" %
                                                    os.environ["SERVER"],
                                                    "-U%s%%%s" %
                                                    (os.environ["USERNAME"],
                                                     os.environ["PASSWORD"]))
                self.assertCmdSuccess(result, out, err, "Ensuring gpo deleted successfully")

            shutil.rmtree(temp_path)
            shutil.rmtree(new_path)

    def test_backup_restore_backup_compare_XML(self):
        """Restore from a static backup and backup to compare XML"""
        static_path = os.path.join(self.backup_path, 'policy',
                                   self.backup_gpo_guid)

        temp_path = os.path.join(self.tempdir, 'temp')
        os.mkdir(temp_path)

        new_path = os.path.join(self.tempdir, 'new')
        os.mkdir(new_path)

        gpo_guid = None
        gpo_guid1 = None
        gpo_guid2 = None
        try:
            (result, out, err) = self.runsubcmd("gpo", "restore", "BACKUP_RESTORE1",
                                                static_path,
                                                "-H", "ldap://%s" %
                                                os.environ["SERVER"], "--tmpdir",
                                                temp_path, "--entities",
                                                self.entity_file, "-U%s%%%s" %
                                                (os.environ["USERNAME"],
                                                 os.environ["PASSWORD"]))

            gpo_guid = "{%s}" % out.split("{")[1].split("}")[0]
            gpo_guid1 = gpo_guid

            (result, out, err) = self.runsubcmd("gpo", "backup", gpo_guid,
                                                "-H", "ldap://%s" %
                                                os.environ["SERVER"],
                                                "--tmpdir", new_path)

            self.assertCmdSuccess(result, out, err, "Ensuring gpo fetched successfully")

            (result, out, err) = self.runsubcmd("gpo", "restore", "BACKUP_RESTORE2",
                                                os.path.join(new_path, 'policy', gpo_guid1),
                                                "-H", "ldap://%s" %
                                                os.environ["SERVER"], "--tmpdir",
                                                temp_path, "--entities",
                                                self.entity_file, "-U%s%%%s" %
                                                (os.environ["USERNAME"],
                                                 os.environ["PASSWORD"]))

            gpo_guid = "{%s}" % out.split("{")[1].split("}")[0]
            gpo_guid2 = gpo_guid

            self.assertCmdSuccess(result, out, err, "Ensuring gpo restored successfully")

            (result, out, err) = self.runsubcmd("gpo", "backup", gpo_guid,
                                                "-H", "ldap://%s" %
                                                os.environ["SERVER"],
                                                "--tmpdir", new_path)

            # Compare the directories
            self.assertIsNone(has_difference(os.path.join(new_path, 'policy',
                                                         gpo_guid1),
                                            os.path.join(new_path, 'policy',
                                                         gpo_guid2),
                                            binary=True, xml=True))
        finally:
            if gpo_guid1:
                (result, out, err) = self.runsubcmd("gpo", "del", gpo_guid1,
                                                    "-H", "ldap://%s" %
                                                    os.environ["SERVER"],
                                                    "-U%s%%%s" %
                                                    (os.environ["USERNAME"],
                                                     os.environ["PASSWORD"]))
                self.assertCmdSuccess(result, out, err, "Ensuring gpo deleted successfully")

            if gpo_guid2:
                (result, out, err) = self.runsubcmd("gpo", "del", gpo_guid2,
                                                    "-H", "ldap://%s" %
                                                    os.environ["SERVER"],
                                                    "-U%s%%%s" %
                                                    (os.environ["USERNAME"],
                                                     os.environ["PASSWORD"]))
                self.assertCmdSuccess(result, out, err, "Ensuring gpo deleted successfully")

            shutil.rmtree(temp_path)
            shutil.rmtree(new_path)

    def test_backup_restore_generalize(self):
        """Restore from a static backup with different entities, generalize it
        again, and compare the XML"""
        static_path = os.path.join(self.backup_path, 'policy',
                                   self.backup_gpo_guid)

        temp_path = os.path.join(self.tempdir, 'temp')
        os.mkdir(temp_path)

        new_path = os.path.join(self.tempdir, 'new')
        os.mkdir(new_path)

        alt_entity_file = os.path.join(new_path, 'entities')
        with open(alt_entity_file, 'wb') as f:
            f.write('''<!ENTITY SAMBA__NETWORK_PATH__82419dafed126a07d6b96c66fc943735__ "\\\\samdom.example.com">
<!ENTITY SAMBA__NETWORK_PATH__0484cd41ded45a0728333a9c5e5ef619__ "\\\\samdom">
<!ENTITY SAMBA____SDDL_ACL____4ce8277be3f630300cbcf80a80e21cf4__ "D:PAR(A;CI;KA;;;BA)(A;CIIO;KA;;;CO)(A;CI;KA;;;SY)(A;CI;KR;;;S-1-16-0)">
<!ENTITY SAMBA____USER_ID_____d0970f5a1e19cb803f916c203d5c39c4__ "*S-1-5-113">
<!ENTITY SAMBA____USER_ID_____7b7bc2512ee1fedcd76bdc68926d4f7b__ "Administrator">
<!ENTITY SAMBA____USER_ID_____a3069f5a7a6530293ad8df6abd32af3d__ "Foobaz">
<!ENTITY SAMBA____USER_ID_____fdf60b2473b319c8c341de5f62479a7d__ "*S-1-5-32-545">
<!ENTITY SAMBA____USER_ID_____adb831a7fdd83dd1e2a309ce7591dff8__ "Guest">
<!ENTITY SAMBA____USER_ID_____9fa835214b4fc8b6102c991f7d97c2f8__ "*S-1-5-32-547">
<!ENTITY SAMBA____USER_ID_____bf8caafa94a19a6262bad2e8b6d4bce6__ "*S-1-5-32-546">
<!ENTITY SAMBA____USER_ID_____a45da96d0bf6575970f2d27af22be28a__ "System">
<!ENTITY SAMBA____USER_ID_____171d33a63ebd67f856552940ed491ad3__ "s-1-5-32-545">
<!ENTITY SAMBA____USER_ID_____7140932fff16ce85cc64d3caab588d0d__ "s-1-1-0">
''')

        gen_entity_file = os.path.join(temp_path, 'entities')

        gpo_guid = None
        try:
            (result, out, err) = self.runsubcmd("gpo", "restore", "BACKUP_RESTORE1",
                                                static_path,
                                                "-H", "ldap://%s" %
                                                os.environ["SERVER"], "--tmpdir",
                                                temp_path, "--entities",
                                                alt_entity_file, "-U%s%%%s" %
                                                (os.environ["USERNAME"],
                                                 os.environ["PASSWORD"]))

            self.assertCmdSuccess(result, out, err, "Ensuring gpo restored successfully")

            gpo_guid = "{%s}" % out.split("{")[1].split("}")[0]

            (result, out, err) = self.runsubcmd("gpo", "backup", gpo_guid,
                                                "-H", "ldap://%s" %
                                                os.environ["SERVER"],
                                                "--tmpdir", new_path,
                                                "--generalize", "--entities",
                                                gen_entity_file)

            self.assertCmdSuccess(result, out, err, "Ensuring gpo fetched successfully")

            # Assert entity files are identical (except for line order)
            self.assertIsNone(has_difference(alt_entity_file,
                                             gen_entity_file,
                                             sortlines=True))

            # Compare the directories (XML)
            self.assertIsNone(has_difference(os.path.join(new_path, 'policy',
                                                         gpo_guid),
                                            static_path, binary=False,
                                            xml=True))
        finally:
            if gpo_guid:
                (result, out, err) = self.runsubcmd("gpo", "del", gpo_guid,
                                                    "-H", "ldap://%s" %
                                                    os.environ["SERVER"],
                                                    "-U%s%%%s" %
                                                    (os.environ["USERNAME"],
                                                     os.environ["PASSWORD"]))
                self.assertCmdSuccess(result, out, err, "Ensuring gpo deleted successfully")

            shutil.rmtree(temp_path)
            shutil.rmtree(new_path)

    def setUp(self):
        """set up a temporary GPO to work with"""
        super(GpoCmdTestCase, self).setUp()
        (result, out, err) = self.runsubcmd("gpo", "create", self.gpo_name,
                                            "-H", "ldap://%s" % os.environ["SERVER"],
                                            "-U%s%%%s" % (os.environ["USERNAME"], os.environ["PASSWORD"]),
                                            "--tmpdir", self.tempdir)
        self.assertCmdSuccess(result, out, err, "Ensuring gpo created successfully")
        shutil.rmtree(os.path.join(self.tempdir, "policy"))
        try:
            self.gpo_guid = "{%s}" % out.split("{")[1].split("}")[0]
        except IndexError:
            self.fail("Failed to find GUID in output: %s" % out)

        self.backup_path = os.path.join(samba.source_tree_topdir(), 'source4',
                                        'selftest', 'provisions',
                                        'generalized-gpo-backup')

        self.entity_file = os.path.join(self.backup_path, 'entities')

    def tearDown(self):
        """remove the temporary GPO to work with"""
        (result, out, err) = self.runsubcmd("gpo", "del", self.gpo_guid, "-H", "ldap://%s" % os.environ["SERVER"], "-U%s%%%s" % (os.environ["USERNAME"], os.environ["PASSWORD"]))
        self.assertCmdSuccess(result, out, err, "Ensuring gpo deleted successfully")
        super(GpoCmdTestCase, self).tearDown()
