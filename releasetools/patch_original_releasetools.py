### This script takes the original releasetools from build/ and generates the bowser releasetools from them
### First arg is your build repo directory, second arg is where you'd like the bowser releasetools output to.
# NOTE: Tested only with Python 3.x
import os, os.path, sys

VERBOSE = True

def strbetween( s, first, last ):
	try:
		start = s.index( first ) + len( first )
		end = s.index( last, start )
		return s[start:end]
	except ValueError:
		return ""

def strbetweenwith( s, first, last ):
	ret = strbetween( s, first, last )
	if ret == "":
		return ret
	return first + ret + last

def verbose_print( s ):
	if VERBOSE:
		print( s )


build_dir = sys.argv[1]
out_dir = sys.argv[2]
releasetools_dir = os.path.join( build_dir, "tools", "releasetools", "" )
otascript_filename = releasetools_dir + "ota_from_target_files"

verbose_print( "Build directory: " + build_dir )
verbose_print( "Out directory: " + out_dir )
verbose_print( "Releasetools directory: " + releasetools_dir )

if not os.path.isdir( build_dir ):
	print( "Build directory not valid!" )
	exit()

if not os.path.isdir( out_dir ):
	print( "Out directory not valid!" )
	exit()

if not os.path.isdir( releasetools_dir ):
	print( "releasetools not found in build directory!" )
	exit()

if not os.path.isfile( otascript_filename ):
	print( "ota_from_target_files not found in releasetools directory!" )
	exit()

otascript_file = open( otascript_filename, "r" )
otascript = otascript_file.read()
otascript_file.close()



## Replace imports
verbose_print( "Replacing imports..." )
otascript = otascript.replace( "import common\nimport edify_generator\n", "import bowser_common as common\nimport bowser_edify_generator as edify_generator\n", 1 )
otascript = otascript.replace( "import add_img_to_target_files\n", "import bowser_add_img_to_target_files as add_img_to_target_files\n", 1 )
verbose_print( "...finished replaced imports." )



## Custom /system format
# Add function
verbose_print( "Adding custom /system formatter..." )
append_assertions_string = strbetweenwith( otascript, "def AppendAssertions(", "\n\n" )
custom_format_function = "# This is a superhacky format just for /system.\n" \
 + "# creates badblock at a predetermined location and fills it with addresses\n" \
 + "def FormatPartitionSystem(self, partition):\n" \
 + "  \"\"\"Format the given partition, specified by its mount point (eg,\n" \
 + "  \"/system\"). mark badblocks from file specified\"\"\"\n" \
 + "  self.script.append('run_program(\"/sbin/sh\", \"-c\", \"echo -e \\'1591\\\\n1592\\' >/tmp/bad\");')\n" \
 + "  fstab = self.info.get(\"fstab\", None)\n" \
 + "  if fstab:\n" \
 + "    p = fstab[partition]\n" \
 + "    self.script.append('run_program(\"/sbin/mke2fs\", \"-t\",\"%s\",\"-l\", \"/tmp/bad\", \"-j\", \"-m0\", \"%s\");' % (p.fs_type, p.device))\n" \
 + "    self.script.append('run_program(\"/sbin/sh\", \"-c\", \"rm -f /tmp/stack; for i in $(seq 1024) ; do echo -ne \\'\\\\\\\\x00\\\\\\\\x50\\\\\\\\x7c\\\\\\\\x80\\' >>/tmp/stack ; done\");')\n" \
 + "    self.script.append('run_program(\"/sbin/dd\", \"if=/tmp/stack\", \"of=%s\", \"bs=6519488\", \"seek=1\", \"conv=notrunc\");' % (p.device))\n" \
 + "\n"
otascript = otascript.replace( append_assertions_string, append_assertions_string + custom_format_function )
# Replace format call with one to new function
format_call_whitespace = "        " # the format call can be found in an if/else block...
format_call_old = "script.FormatPartition(\"/system\")\n"
format_call_new = "FormatPartitionSystem(script, \"/system\")\n"
while len( format_call_whitespace ) > 0: # ...so the whitespace needs to be matched up
	if otascript.count( format_call_whitespace + format_call_old ) == 1:
		break
	format_call_whitespace = format_call_whitespace[:-2]
otascript = otascript.replace( format_call_whitespace + format_call_old, format_call_whitespace + "#" + format_call_old + format_call_whitespace + format_call_new, 1 )
verbose_print( "...finished adding custom /system formatter." )



## Force non-block-based OTA in WriteFullOTAPackage
block_based_search = "  block_based = "
if otascript.count( block_based_search ) >= 1:
	verbose_print( "Forcing non-block OTA..." )
	block_based_old = strbetweenwith( otascript, block_based_search, "\n" )
	block_based_new = "  #" + block_based_old[2:] + "  block_based = False\n"
	otascript = otascript.replace( block_based_old, block_based_new, 1 )
	verbose_print( "...finished forcing non-block OTA." )
else:
	verbose_print( "Skipped forcing non-block OTA." )



## Force disable two-step
two_step_elif = "elif o in (\"-2\", \"--two_step\"):\n"
if otascript.count( two_step_elif ) >= 1:
	verbose_print( "Force disabling two-step..." )
	two_step_set = "  OPTIONS.two_step = True\n"
	two_step_whitespace = strbetween( otascript, two_step_elif, two_step_set )
	two_step_old = two_step_elif + two_step_whitespace + two_step_set
	two_step_new = "#" + two_step_elif + two_step_whitespace + "#" + two_step_set
	otascript = otascript.replace( two_step_old, two_step_new )
	verbose_print( "...finished force disabling two-step." )
else:
	verbose_print( "Skipped disabling two-step." )



## Keep boot.img as made by boot.mk
get_boot_img_old_one = "boot_img = common.GetBootableImage(\"boot.img\", \"boot.img\",\n  "
if otascript.count( get_boot_img_old_one ) >= 1:
	verbose_print( "Patching boot image to keep one done by boot.mk..." )
	get_boot_img_old_two = strbetween( otascript, get_boot_img_old_one, "\n" ) + "\n"
	get_boot_img_new = "# This seems to be a very bad hack and the second reason why we have\n" \
	+ "  # releasetools in device/amazon/bowser\n" \
	+ "  # FIX ME!!!\n" \
	+ "  print \"For bowser we keep the boot.img as done by boot.mk\"\n" \
	+ "  boot_img = common.File.FromLocalFile(\"boot.img\",\n" \
	+ "                                        os.environ.get('ANDROID_PRODUCT_OUT') + \"/boot.img\")\n" \
	+ "  #" + get_boot_img_old_one \
	+ "#" + get_boot_img_old_two
	otascript = otascript.replace( get_boot_img_old_one + get_boot_img_old_two, get_boot_img_new )
	verbose_print( "...finished patching boot image to keep one done by boot.mk." )
	# Don't check boot image size
	boot_img_size_old = "common.CheckSize(boot_img"
	if otascript.count( boot_img_size_old ) >= 1:
		verbose_print( "Disabling boot.img size check..." )
		boot_img_size_new = "# Don't check size of boot.img. It's VERY close to max and this will fail\n  #" + boot_img_size_old
		otascript = otascript.replace( boot_img_size_old, boot_img_size_new )
		verbose_print( "...finished disabling boot.img size check." )
	else:
		verbose_print( "Skipping disabling boot.img size check." )
else:
	verbose_print( "Skipping patching boot image to keep one done by boot.mk." )



## Misc
verbose_print( "Doing miscellaneous patches..." )
recovery_img_one = "recovery_img = common.GetBootableImage(\"recovery.img\", \"recovery.img\",\n  "
recovery_img_two = "OPTIONS.input_tmp, \"RECOVERY\")\n"
recovery_img_two = strbetween( otascript, recovery_img_one, recovery_img_two ) + recovery_img_two
if otascript.count( recovery_img_one + recovery_img_two ) == 1:
	otascript = otascript.replace( recovery_img_one, "#" + recovery_img_one, 1 )
	otascript = otascript.replace( recovery_img_two, "#" + recovery_img_two, 1 )

recovery_patch_if = "if not has_recovery_patch:\n"
if otascript.count( recovery_patch_if ) == 1:
	otascript = otascript.replace( recovery_patch_if, "#" + recovery_patch_if, 1 )

recovery_system_unpack = "script.UnpackPackageDir(\"recovery\", \"/system\")"
otascript = otascript.replace( recovery_system_unpack, "#" + recovery_system_unpack )

make_recovery_patch_old_one = "  common.MakeRecoveryPatch(OPTIONS.input_tmp, output_sink,\n  "
make_recovery_patch_old_two = "recovery_img, boot_img)\n"
make_recovery_patch_whitespace = strbetween( otascript, make_recovery_patch_old_one, make_recovery_patch_old_two )
make_recovery_patch_old = make_recovery_patch_old_one + make_recovery_patch_whitespace + make_recovery_patch_old_two
make_recovery_patch_new = "#" + make_recovery_patch_old_one + "#" + make_recovery_patch_whitespace + make_recovery_patch_old_two
otascript = otascript.replace( make_recovery_patch_old, make_recovery_patch_new )


recovery_wipeout_old = "source_recovery = " + strbetween( otascript, "source_recovery = ", "\n  updating_recovery = " )
recovery_wipeout_new = "#" + recovery_wipeout_old.replace( "\n  ", "\n  #" )
otascript = otascript.replace( recovery_wipeout_old, recovery_wipeout_new )

updating_recovery_old = strbetweenwith( otascript, "  updating_recovery = ", "\n" )
updating_recovery_new = "  #" + updating_recovery_old[2:] + "  updating_recovery = False\n"
otascript = otascript.replace( updating_recovery_old, updating_recovery_new )
verbose_print( "...finished miscellaneous patches." )

outfile = open( out_dir + "bowser_ota_from_target_files.py", "w" )
outfile.write( otascript )
outfile.close()
