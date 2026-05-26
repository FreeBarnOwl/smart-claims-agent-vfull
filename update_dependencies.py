#!/usr/bin/env python3
"""
Safe Dependency Update Manager
Provides guided dependency updates with safety checks
"""
import subprocess
import sys
import json
from typing import List, Dict, Tuple
from pathlib import Path
import shutil

class DependencyUpdater:
    def __init__(self):
        self.backup_dir = Path("dependency_backups")
        self.requirements_files = [
            "backend/requirements.txt",
            "frontend/requirements.txt"
        ]

    def create_backup(self):
        """Create backup of current requirements files"""
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
        self.backup_dir.mkdir()

        print("📁 Creating backup of current requirements...")
        for req_file in self.requirements_files:
            if Path(req_file).exists():
                backup_path = self.backup_dir / Path(req_file).name
                shutil.copy2(req_file, backup_path)
                print(f"  ✓ Backed up {req_file}")

    def restore_backup(self):
        """Restore from backup if something goes wrong"""
        print("🔙 Restoring from backup...")
        for req_file in self.requirements_files:
            backup_path = self.backup_dir / Path(req_file).name
            if backup_path.exists():
                shutil.copy2(backup_path, req_file)
                print(f"  ✓ Restored {req_file}")

    def get_outdated_packages(self, req_file: str) -> List[Dict]:
        """Get list of outdated packages for a requirements file"""
        print(f"🔍 Checking outdated packages in {req_file}...")

        try:
            # Parse current requirements
            current_packages = {}
            with open(req_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '==' in line:
                        name, version = line.split('==', 1)
                        if '[' in name:
                            name = name.split('[')[0]
                        current_packages[name.strip()] = version.strip()

            # Get latest versions from PyPI
            outdated = []
            for package, current_version in current_packages.items():
                try:
                    import urllib.request
                    import json

                    url = f"https://pypi.org/pypi/{package}/json"
                    req = urllib.request.Request(url)
                    req.add_header('User-Agent', 'DependencyUpdater/1.0')

                    with urllib.request.urlopen(req, timeout=10) as response:
                        data = json.loads(response.read().decode('utf-8'))
                        latest_version = data['info']['version']

                        if latest_version != current_version:
                            # Simple version comparison
                            current_parts = [int(x) for x in current_version.split('.')]
                            latest_parts = [int(x) for x in latest_version.split('.')]

                            if current_parts < latest_parts:
                                update_type = "patch"
                                if len(current_parts) > 0 and len(latest_parts) > 0:
                                    if latest_parts[0] > current_parts[0]:
                                        update_type = "major"
                                    elif len(current_parts) > 1 and len(latest_parts) > 1 and latest_parts[1] > current_parts[1]:
                                        update_type = "minor"

                                outdated.append({
                                    'name': package,
                                    'current': current_version,
                                    'latest': latest_version,
                                    'update_type': update_type
                                })

                except Exception as e:
                    print(f"  ⚠️ Could not check {package}: {e}")

            return outdated

        except Exception as e:
            print(f"❌ Error checking {req_file}: {e}")
            return []

    def update_package_in_file(self, req_file: str, package: str, new_version: str):
        """Update a package version in requirements file"""
        try:
            with open(req_file, 'r') as f:
                lines = f.readlines()

            updated_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and '==' in stripped:
                    name, version = stripped.split('==', 1)
                    if '[' in name:
                        name = name.split('[')[0]

                    if name.strip() == package:
                        # Update this line
                        if '[' in line:  # Handle extras like uvicorn[standard]
                            package_with_extras = line.split('==')[0]
                            updated_lines.append(f"{package_with_extras}=={new_version}\n")
                        else:
                            updated_lines.append(f"{package}=={new_version}\n")
                    else:
                        updated_lines.append(line)
                else:
                    updated_lines.append(line)

            with open(req_file, 'w') as f:
                f.writelines(updated_lines)

            print(f"  ✓ Updated {package} to {new_version} in {req_file}")

        except Exception as e:
            print(f"❌ Error updating {package}: {e}")

    def test_installation(self, req_file: str) -> bool:
        """Test if requirements can be installed successfully"""
        print(f"🧪 Testing installation of {req_file}...")

        try:
            # Create temporary virtual environment for testing
            test_venv = Path("temp_test_venv")
            if test_venv.exists():
                shutil.rmtree(test_venv)

            # Create venv and test install
            result = subprocess.run([
                sys.executable, '-m', 'venv', str(test_venv)
            ], capture_output=True, text=True)

            if result.returncode != 0:
                print(f"❌ Could not create test environment")
                return False

            # Install requirements in test environment
            if sys.platform == "win32":
                pip_path = test_venv / "Scripts" / "pip"
            else:
                pip_path = test_venv / "bin" / "pip"

            result = subprocess.run([
                str(pip_path), 'install', '-r', req_file, '--no-cache-dir'
            ], capture_output=True, text=True, timeout=300)

            # Cleanup
            shutil.rmtree(test_venv)

            if result.returncode == 0:
                print(f"  ✅ Installation test passed")
                return True
            else:
                print(f"  ❌ Installation test failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print(f"  ⏰ Installation test timed out")
            return False
        except Exception as e:
            print(f"  ❌ Error during installation test: {e}")
            return False

    def run_interactive_update(self):
        """Run interactive dependency update process"""
        print("🚀 Safe Dependency Update Manager")
        print("=" * 50)

        # Create backup
        self.create_backup()

        try:
            for req_file in self.requirements_files:
                if not Path(req_file).exists():
                    print(f"⚠️ Requirements file {req_file} not found, skipping...")
                    continue

                print(f"\n📋 Processing {req_file}")
                print("-" * 30)

                outdated = self.get_outdated_packages(req_file)

                if not outdated:
                    print("✅ All packages are up to date!")
                    continue

                print(f"\n📦 Found {len(outdated)} outdated packages:")
                print("\nPackage updates available:")
                print(f"{'Package':<20} {'Current':<15} {'Latest':<15} {'Type':<10}")
                print("-" * 65)

                for pkg in outdated:
                    update_type = pkg['update_type'].upper()
                    emoji = {"MAJOR": "🔴", "MINOR": "🟡", "PATCH": "🟢"}.get(update_type, "❓")
                    print(f"{pkg['name']:<20} {pkg['current']:<15} {pkg['latest']:<15} {emoji} {update_type:<10}")

                print(f"\nUpdate strategy recommendations:")
                print("🟢 PATCH: Safe to update (bug fixes)")
                print("🟡 MINOR: Generally safe (new features)")
                print("🔴 MAJOR: Review carefully (breaking changes)")

                response = input(f"\nProceed with updates for {req_file}? (y/n/selective): ").lower()

                if response == 'n':
                    print("⏭️ Skipping updates for this file")
                    continue

                packages_to_update = []

                if response == 'selective':
                    print("\n🎯 Selective Update Mode")
                    for pkg in outdated:
                        update_response = input(f"Update {pkg['name']} {pkg['current']} → {pkg['latest']} ({pkg['update_type']})? (y/n): ").lower()
                        if update_response == 'y':
                            packages_to_update.append(pkg)
                else:
                    packages_to_update = outdated

                if not packages_to_update:
                    print("⏭️ No packages selected for update")
                    continue

                # Apply updates
                print(f"\n🔄 Applying {len(packages_to_update)} updates...")
                success_count = 0

                for pkg in packages_to_update:
                    try:
                        self.update_package_in_file(req_file, pkg['name'], pkg['latest'])
                        success_count += 1
                    except Exception as e:
                        print(f"❌ Failed to update {pkg['name']}: {e}")

                print(f"\n✅ Successfully updated {success_count}/{len(packages_to_update)} packages")

                # Test installation
                test_response = input("🧪 Test installation of updated requirements? (y/n): ").lower()
                if test_response == 'y':
                    if not self.test_installation(req_file):
                        print("❌ Installation test failed!")
                        restore_response = input("🔙 Restore from backup? (y/n): ").lower()
                        if restore_response == 'y':
                            self.restore_backup()
                            print("✅ Restored from backup")
                            continue

            print("\n🎉 Update process completed!")
            print("\n📋 Next steps:")
            print("1. Run your test suite: `python -m pytest`")
            print("2. Test the application functionality")
            print("3. Commit changes if everything works")
            print("4. Update your CI/CD to use new versions")

        except KeyboardInterrupt:
            print("\n\n⚠️ Update process interrupted")
            restore_response = input("🔙 Restore from backup? (y/n): ").lower()
            if restore_response == 'y':
                self.restore_backup()
                print("✅ Restored from backup")

        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            self.restore_backup()
            print("✅ Restored from backup")

def main():
    updater = DependencyUpdater()

    if len(sys.argv) > 1:
        if sys.argv[1] == '--backup':
            updater.create_backup()
            print("✅ Backup created")
            return
        elif sys.argv[1] == '--restore':
            updater.restore_backup()
            print("✅ Restored from backup")
            return
        elif sys.argv[1] == '--test':
            for req_file in updater.requirements_files:
                if Path(req_file).exists():
                    success = updater.test_installation(req_file)
                    print(f"Test result for {req_file}: {'✅ PASS' if success else '❌ FAIL'}")
            return

    updater.run_interactive_update()

if __name__ == "__main__":
    print("Usage examples:")
    print("  python update_dependencies.py           # Interactive update")
    print("  python update_dependencies.py --backup  # Create backup only")
    print("  python update_dependencies.py --restore # Restore from backup")
    print("  python update_dependencies.py --test    # Test current requirements")
    print()
    main()