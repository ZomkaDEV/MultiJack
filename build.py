import ast
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import importlib.metadata
import PyInstaller.__main__

def check_dependencies():
    with open("requirements.txt", 'r') as f:
        required_packages = f.readlines()

    required_packages = [pkg.strip() for pkg in required_packages if pkg.strip() and not pkg.startswith('#')]

    missing_packages = []

    for package in required_packages:
        package_name = package.split('==')[0]
        try:
            importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            missing_packages.append(package_name)

    return missing_packages


def get_version_from_main():
    with open('main.py', 'r') as file:
        tree = ast.parse(file.read(), filename='main.py')
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'version':
                        return node.value.value
    return None

def get_adddata_arg():
    if sys.platform == "win32":
        return "--add-data", "localization.json;."
    else:
        return "--add-data", "localization.json:."

def get_version_file():
    if sys.platform == "win32":
        return "--version-file", "version.txt"
    else:
        return ""

def get_icon_arg():
    match sys.platform:
        case "win32":
            return "-i", "icon.ico"
        case "darwin":
            return "-i", "icon.icns"
        case _:
            return ""


def generate_version_file(version):
    version_parts = version.split('.')
    major, minor, patch = version_parts[0], version_parts[1], version_parts[2] if len(version_parts) > 2 else "0"
    # TODO: implement adding build number to the version
    build = 0

    rc_content = f"""# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3f,
    flags=0x0,
    OS=0x4,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [StringStruct(u'FileDescription', u'Maintain multiple instances of Jackbox with ease!'),
           StringStruct(u'FileVersion', u'{version}'),
           StringStruct(u'LegalCopyright', u'Zomka'),
           StringStruct(u'ProductName', u'MultiJack'),
           StringStruct(u'ProductVersion', u'{version}')])
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    with open('version.txt', 'w') as file:
        file.write(rc_content)
    print(f"Version file 'version.txt' created with version {version}")

def main():
    global issc
    bars = "-----------------------------"

    if not check_dependencies():
        print(bars)
        print("You didn't install the necessary dependencies!")
        print("Run `python -m pip install -r requirements` in a venv and then run this script again.")
        print(bars)

    version = get_version_from_main()
    if not version:
        print(bars)
        print("Failed retrieving the version from main.py")
        print(bars)
        sys.exit(1)

    print(f"Building version: {version}")

    #Clear remains of old artifacts
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("Output"):
        shutil.rmtree("Output")
    if os.path.exists("Output"):
        shutil.rmtree("Output")
    if os.path.exists(f"MultiJack-{version}-macOS-{platform.machine()}.dmg"):
        os.remove(f"MultiJack-{version}-macOS-{platform.machine()}.dmg")

    if sys.platform == "win32":
        issc = "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"
        if not os.path.exists(issc):
            if not os.path.exists(sys.argv[1]) and not sys.argv[1].endswith("ISCC.exe"):
                print(bars)
                print("Please specify location of Inno Setup before running the command!")
                print("Like so:")
                print("python build.py path\\to\\ISCC.exe")
                print(bars)
                sys.exit(1)
            else:
                issc = sys.argv[1]

        generate_version_file(version)
    try:
        PyInstaller.__main__.run(["main.py", "--windowed", "-D", "-n", "MultiJack", *get_icon_arg(), *get_adddata_arg(), *get_version_file(), "--clean"])
    except:
        print(bars)
        print("Build failed!")
        print(bars)
        sys.exit(1)

    if os.path.exists("version.txt"):
        os.remove("version.txt")

    if sys.platform == "win32":
        print(bars)
        print("Compiling the installer...")
        print(bars)
        try:
            subprocess.run([issc, ".\\installer.iss", f"/DAppVersion={version}", f"/DAppArch={platform.machine()}"])
        except:
            print(bars)
            print("Compiling the installer failed!")
            print(bars)
    elif sys.platform == "darwin":
        if shutil.which("create-dmg") is None:
            if shutil.which("brew") is None:
                print(bars)
                print("Please install create-dmg and return!")
                print(bars)
                sys.exit(1)
            else:
                print(bars)
                print("Installing create-dmg using Homebrew...")
                print(bars)
                subprocess.run(["brew", "install", "create-dmg"])
        try:
            # We don't need the non-.app build
            shutil.rmtree("dist/MultiJack/")

            subprocess.run([
                "create-dmg",
                "--volname", "MultiJack Installer",
                "--volicon", "icon.icns",
                "--window-pos", "200", "120",
                "--window-size", "800", "400",
                "--icon-size", "100",
                "--icon", "MultiJack.app", "200", "190",
                "--hide-extension", "MultiJack.app",
                "--app-drop-link", "600", "185",
                f"MultiJack-{version}-macOS-{platform.machine()}.dmg",
                "dist/"
            ])
        except:
            print(bars)
            print("Building the DMG failed!")
            print(bars)
            sys.exit(1)
    elif sys.platform == "linux":
        print(bars)
        print("Creating tarball and compressing it with gzip...")
        print(bars)
        with tarfile.open(f"dist/MultiJack-{version}-Linux-{platform.machine()}.tar.gz", "w:gz") as tar:
            tar.add("dist/MultiJack/", arcname="MultiJack")

    print(bars)
    print("Build completed!")
    match sys.platform:
        case "win32":
            print("You can find the installer in the \"Output\" folder")
        case "darwin":
            print(f"The DMG file is \"./MultiJack-{version}-macOS-{platform.machine()}.dmg\"")
        case "linux":
            print(f"You can find the build in \"dist/MultiJack-{version}-Linux-{platform.machine()}.tar.gz\"")
    print(bars)

if __name__ == "__main__":
    main()
