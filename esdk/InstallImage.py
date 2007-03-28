#!/usr/bin/python -tt
# vim: ai ts=4 sts=4 et sw=4

import os, sys, re, tempfile, shutil

import SDK
import Project
import Mkinitrd

class SyslinuxCfg(object):
    def __init__(self, path, cfg_filename):
        self.path = path
        self.cfg_path = os.path.join(self.path, cfg_filename)
        self.msg_path = os.path.join(self.path, 'boot.msg')
        self.index = 1

        welcome_mesg = "Welcome to the Linux eSDK:"

        # Create and initialize the syslinux config file
        cfg_file = open(self.cfg_path, 'w')
        print >> cfg_file, """\
prompt 1
timeout 600
display boot.msg
"""
        cfg_file.close()

        # Create and initialize the syslinux boot message file
        msg_file = open(self.msg_path, 'w')
        msg_file.write("\f")
        print >> msg_file, "\n" + welcome_mesg + "\n"
        msg_file.close()

    def add_default(self, kernel, append = 'initrd=initrd.img'):
        label = 'linux'
        kernel_file = 'vmlinuz'

        # Add the default entry to the syslinux config file
        cfg_file = open(self.cfg_path, 'a ')
        print >> cfg_file, "default " + label
        print >> cfg_file, "label " + label
        print >> cfg_file, "  kernel " + kernel_file
        print >> cfg_file, "  append " + append
        cfg_file.close()

        # Add the default entry in the syslinux boot message file
        msg_file = open(self.msg_path, 'a ')
        msg_file.write("- To boot default " + kernel + " kernel, press " + chr(15) + \
                       "\x01<ENTER>" +  chr(15) + "\x07\n\n")
        msg_file.close()
        return kernel_file

    def add_target(self, kernel, append = 'initrd=initrd.img'):
        label = "linux%s" % self.index
        kernel_file = "linux%s" % self.index
        self.index += 1

        # Add the target to the syslinux config file
        cfg_file = open(self.cfg_path, 'a ')
        print >> cfg_file, "label " + label
        print >> cfg_file, "  kernel " + kernel_file
        print >> cfg_file, "  append " + append
        cfg_file.close()

        # Add the target to the syslinux boot message file
        msg_file = open(self.msg_path, 'a ')
        msg_file.write("- To boot " + kernel + " kernel, type: " + chr(15) + \
                       "\x01" + label + " <ENTER>" +  chr(15) + "\x07\n\n")
        msg_file.close()
        return kernel_file


class InstallImage(object):
    """
    This is the base class for any type of target image output.

    This is used as the super-class for sub-classes that will generate
    installation images for a specific target and for a specific class
    of installation device/medium. Such as installation of a target system
    on a LiveUSB Key, LiveCD/DVD's, Hard Disks, and Flash Parts.
    """
    def __init__(self, project, target, name):
        self.project = project
        self.target = target
        self.name = name
        self.path = os.path.join(self.target.image_path, self.name)
        self.tmp_path = ''

    def install_kernels(self, cfg_filename):
        if not self.tmp_path:
            raise ValueError, "tmp_path doesn't exist"

        # Find installed kernels on target filesystem
        kernels = []
        for file in os.listdir(os.path.join(self.target.fs_path, 'boot')):
            if file.find('vmlinuz') == 0:
                kernels.append(file)

        if not kernels:
            raise ValueError, "no kernels were found"

        # Sort the kernels, first kernel is the default kernel
        kernels.sort()
        
        s = SyslinuxCfg(self.tmp_path, cfg_filename)

        # Copy the default kernel
        default_kernel = kernels.pop(0)
        kernel_name = s.add_default(default_kernel, 'initrd=initrd.img root=rootfs.img')
        src_path = os.path.join(self.target.fs_path, 'boot')
        src_path = os.path.join(src_path, default_kernel)
        dst_path = os.path.join(self.tmp_path, kernel_name)
        shutil.copyfile(src_path, dst_path)

        # Copy the remaining kernels
        for k in kernels:
            kernel_name = s.add_target(k, 'initrd=initrd.img root=rootfs.img')
            src_path = os.path.join(self.target.fs_path, 'boot')
            src_path = os.path.join(src_path, k)
            dst_path = os.path.join(self.tmp_path, kernel_name)
            shutil.copyfile(src_path, dst_path)

    def create_fstab(self):
        fstab_file = open(os.path.join(self.target.fs_path, 'etc/fstab'), 'w')
        print >> fstab_file, """\
/dev/devpts             /dev/pts                devpts  gid=5,mode=620  0 0
/dev/shm                /dev/shm                tmpfs   defaults        0 0
/dev/proc               /proc                   proc    defaults        0 0
/dev/sys                /sys                    sysfs   defaults        0 0

"""
        fstab_file.close()

    def create_modules_dep(self):
        base_dir = self.target.fs_path[len(self.project.path):]
        boot_path = os.path.join(self.target.fs_path, 'boot')
        
        for file in os.listdir(boot_path):
            if file.find('System.map-') == 0:
                kernel_version = file[len('System.map-'):]

                tmp_str = "lib/modules/%s/modules.dep" % kernel_version
                moddep_file = os.path.join(self.target.fs_path, tmp_str)

                if os.path.isfile(moddep_file):
                    sr_deps = os.stat(moddep_file)
                    sr_sym  = os.stat(os.path.join(boot_path, file))
                    
                    # Skip generating a new modules.dep if the Symbols are
                    # older than the current modules.dep file.
                    if sr_deps.st_mtime > sr_sym.st_mtime: 
                        continue

                symbol_file = os.path.join(base_dir, 'boot')
                symbol_file = os.path.join(symbol_file, file)

                cmd_args = "-b %s -v %s -F %s" % (base_dir, kernel_version, symbol_file)
                self.project.chroot("/sbin/depmod", cmd_args)

    def create_rootfs(self):
        if not os.path.isfile(os.path.join(self.target.fs_path, 'etc/fstab')):
            self.create_fstab()

        self.create_modules_dep()

        self.rootfs = 'rootfs.img'
        self.rootfs_path = os.path.join(self.target.image_path, self.rootfs)
        if os.path.isfile(self.rootfs_path):
            os.remove(self.rootfs_path)
        
        jail_path = self.path[len(self.project.path):]
        self.project.chroot('/usr/bin/syslinux', jail_path)

        fs_path    = self.target.fs_path[len(self.project.path):]
        image_path = self.target.image_path[len(self.project.path):]
        image_path = os.path.join(image_path,'rootfs.img')
        cmd_args = "%s %s" % (fs_path, image_path)

        self.project.chroot("/sbin/mksquashfs", cmd_args)

    def create_install_script(self, path):
        install_file = open(os.path.join(path, 'install.sh'), 'w')
        print >> install_file, """\
#!/bin/bash

echo -e '\nDeleting Partition Table on /dev/hda...\n'
dd if=/dev/zero of=/dev/hda bs=512 count=2
sync

echo -e 'Creating New Partiton Table on /dev/hda...\n'
fdisk /dev/hda <<EOF
n
p
1
1
+1024M
n
p
2


a
1
w
EOF

sync

echo -e 'Formatting /dev/hda1 w/ ext2...\n'
mkfs.ext2 /dev/hda1
sync

echo -e 'Formatting /dev/hda2 w/ ext3...\n'
mkfs.ext3 /dev/hda2
sync

echo -e 'Mounting partitions...\n'
mkdir /tmp/install
mount /dev/sda /tmp/install

mount /dev/hda2 /mnt
mkdir /mnt/boot
mount /dev/hda1 /mnt/boot

echo -e 'Copying system files onto hard disk drive...\n'
cp -v /tmp/install/rootfs.img /mnt/boot
cp -av /boot/ /mnt

grub-install --root-directory=/mnt /dev/hda

cat > /mnt/boot/grub/grub.conf <<EOF
# grub.conf generated by platform install script
#
# Note that you do not have to rerun grub after making changes to this file
# NOTICE:  You have a /boot partition.  This means that
#          all kernel and initrd paths are relative to /boot/, eg.
#          root (hd0,0)
#          kernel /vmlinuz-version ro root=/dev/sda3
#          initrd /initrd-version.img
#boot=/dev/sda
default=1
timeout=5
splashimage=(hd0,0)/grub/splash.xpm.gz
hiddenmenu
title Linux (2.6.20-default)
	root (hd0,0)
	kernel /vmlinuz-2.6.20-default ro rhgb
	initrd /initrd-2.6.20-default.img
title Linux (2.6.20-developer)
	root (hd0,0)
	kernel /vmlinuz-2.6.20-developer ro rhgb
	initrd /initrd-2.6.20-developer.img
EOF

ln -s ./grub.conf /mnt/boot/grub/menu.lst

umount /mnt/boot
umount /mnt

echo -e '\n\n\nInstall Finished!\n\n'
echo -e 'System shuting down!\n\n'
echo -e 'Disconnect the USB-Key when shutdown is complete and\n'
echo -e 'Reboot the system from HDD...\n\n'

exec init -t10 0
"""
        install_file.close()

        
    def __str__(self):
        return ("<InstallImage: project=%s, target=%s, name=%s>"
                % (self.project, self.target, self.name))


class LiveIsoImage(InstallImage):
    def create_image(self):
        raise ValueError("LiveIsoImage: Create ISO Image not implemented!")
        
    def __str__(self):
        return ("<LiveIsoImage: project=%s, target=%s, name=%s>"
                % (self.project, self.target, self.name))


class InstallIsoImage(InstallImage):
    def create_image(self):
        raise ValueError("InstallIsoImage: Create Install ISO Image not implemented!")
        
    def __str__(self):
        return ("<InstallIsoImage: project=%s, target=%s, name=%s>"
                % (self.project, self.target, self.name))


class BaseUsbImage(InstallImage):
    def install_kernels(self):
        InstallImage.install_kernels(self, 'syslinux.cfg')
        
    def create_container_file(self, size):
        cmd_line = "dd if=/dev/zero of=%s bs=1M count=%s" % (self.path, size)
        os.system(cmd_line)

        cmd_line = "/sbin/mkfs.vfat %s" % self.path
        os.system(cmd_line)

        # NOTE: Running syslinux on the host development system
        #       means the host and target have compatible architectures.
        #       This runs syslinux inside the jailroot so the correct
        #       version of syslinux is used.
        jail_path = self.path[len(self.project.path):]
        self.project.chroot('/usr/bin/syslinux', jail_path)

    def mount_container(self):
        if not self.tmp_path:
            self.tmp_path = tempfile.mkdtemp('','esdk-', '/tmp')
            cmd_line = "mount -o loop -t vfat %s %s" % (self.path, self.tmp_path)
            os.system(cmd_line)

    def umount_container(self):
        if self.tmp_path:
            cmd_line = "umount %s" % self.tmp_path
            os.system(cmd_line)
            os.rmdir(self.tmp_path)
            self.tmp_path = ''

class LiveUsbImage(BaseUsbImage):
    def create_image(self):
        print "LiveUsbImage: Creating LiveUSB Image Now!"

        self.create_rootfs()

        stat_result = os.stat(self.rootfs_path)
        size = (stat_result.st_size / (1024 * 1024)) + 16

        self.create_container_file(size)

        self.mount_container()

        initrd_path = os.path.join(self.tmp_path, 'initrd.img')
        Mkinitrd.create(self.project, initrd_path)
        
        self.install_kernels()

        shutil.copy(self.rootfs_path, self.tmp_path)

        self.umount_container()

        print "LiveUsbImage: Finished!"
        
    def __str__(self):
        return ("<LiveUsbImage: project=%s, target=%s, name=%s>"
                % (self.project, self.target, self.name))


class InstallUsbImage(BaseUsbImage):
    def create_image(self):
        print "InstallUsbImage: Creating InstallUSB Image Now!"

        self.create_rootfs()

        stat_result = os.stat(self.rootfs_path)
        size = (stat_result.st_size / (1024 * 1024)) + 16

        self.create_container_file(size)

        self.mount_container()

        initrd_path = os.path.join(self.tmp_path, 'initrd.img')
        Mkinitrd.create(self.project, initrd_path)
        
        self.install_kernels()

        shutil.copy(self.rootfs_path, self.tmp_path)

        self.create_install_script(self.tmp_path)
        self.umount_container()

        print "InstallUsbImage: Finished!"
        print "\nYou can now use the image to boot and install the target file-system on the target device's HDD.\n"
        print "\nWARNING: Entire contents of the target devices's HDD will be erased prior to installation!"
        print "         This includes ALL partitions on the disk!\n"
        
    def __str__(self):
        return ("<InstallUsbImage: project=%s, target=%s, name=%s>"
                % (self.project, self.target, self.name))


class HddImage(InstallImage):
    def create_image(self):
        raise ValueError("HddImage: Create Hard Disk Image not implemented!")
        
    def __str__(self):
        return ("<HddImage: project=%s, target=%s, name=%s>"
                % (self.project, self.target, self.name))



if __name__ == '__main__':
    cnt = len(sys.argv)
    if (cnt != 4) and (cnt != 2):
        print >> sys.stderr, "USAGE: %s proj_path proj_name platform_name" % (sys.argv[0])
        print >> sys.stderr, "       %s proj_name" % (sys.argv[0])
        sys.exit(1)

    sdk = SDK.SDK()

    if cnt == 4:
        proj_path = sys.argv[1]
        proj_name = sys.argv[2]
        platform_name = sys.argv[3]

        proj = sdk.create_project(proj_path, proj_name, 'test project', sdk.platforms[platform_name])
        proj.install()

        target = proj.create_target('mytest')
        target.install(sdk.platforms[platform_name].fset['Core'])

    else:
        proj_name = sys.argv[1]
        proj = sdk.projects[proj_name]

    proj.mount()

    imgLiveIso = LiveIsoImage(proj, proj.targets['mytest'], "mytest_v1-Live-DVD.iso")
    print "\nImage File Name: %s" % imgLiveIso.name
    imgLiveIso.create_image()

    imgInstallIso = InstallIsoImage(proj, proj.targets['mytest'], "mytest_v2-Install-DVD.iso")
    print "\nImage File Name: %s" % imgInstallIso.name
    imgInstallIso.create_image()

    imgLiveUsb = LiveUsbImage(proj, proj.targets['mytest'], "mytest_v3-Live-USB.bin")
    print "\nImage File Name: %s" % imgLiveUsb.name
    imgLiveUsb.create_image()

    imgInstallUsb = InstallUsbImage(proj, proj.targets['mytest'], "mytest_v4-Install-USB.bin")
    print "\nImage File Name: %s" % imgInstallUsb.name
    imgInstallUsb.create_image()

    imgHdd = HddImage(proj, proj.targets['mytest'], "mytest_v5-HDD.tar.bz2")
    print "\nImage File Name: %s" % imgHdd.name
    imgHdd.create_image()

    print "\n\nFinish!\n"
    
