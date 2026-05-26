#!/usr/bin/env python3
"""
Comprehensive Dependency Security and Compliance Audit
"""
import json
import re
import sys
from urllib.request import urlopen, Request
from urllib.error import URLError
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
# from packaging import version  # Will be imported later
from datetime import datetime, timedelta

@dataclass
class VulnerabilityInfo:
    package: str
    current_version: str
    vulnerability_id: str
    severity: str
    description: str
    affected_versions: str
    fixed_in: str = ""

@dataclass
class DependencyInfo:
    name: str
    current_version: str
    latest_version: str = ""
    license: str = ""
    description: str = ""
    size_bytes: int = 0
    last_updated: str = ""
    vulnerabilities: List[VulnerabilityInfo] = None

    def __post_init__(self):
        if self.vulnerabilities is None:
            self.vulnerabilities = []

class DependencyAuditor:
    def __init__(self):
        self.pypi_base_url = "https://pypi.org/pypi"

        # Known vulnerability data (simplified for demo - in production use proper CVE databases)
        self.known_vulnerabilities = {
            "pillow": [
                {
                    "versions": ["<10.3.0"],
                    "cve": "CVE-2024-28219",
                    "severity": "HIGH",
                    "description": "Buffer overflow in libwebp"
                }
            ],
            "httpx": [
                {
                    "versions": ["<0.27.0"],
                    "cve": "CVE-2024-37891",
                    "severity": "MEDIUM",
                    "description": "Cookie domain validation bypass"
                }
            ],
            "fastapi": [
                {
                    "versions": ["<0.110.1"],
                    "cve": "CVE-2024-24762",
                    "severity": "HIGH",
                    "description": "Path traversal via filename parameter"
                }
            ]
        }

        # License compatibility matrix
        self.license_compatibility = {
            'MIT': ['MIT', 'BSD', 'Apache-2.0', 'ISC'],
            'Apache-2.0': ['Apache-2.0', 'MIT', 'BSD'],
            'GPL-3.0': ['GPL-3.0', 'GPL-2.0'],
            'BSD-3-Clause': ['BSD-3-Clause', 'MIT', 'Apache-2.0'],
        }

    def compare_versions(self, version1: str, version2: str) -> int:
        """Simple version comparison. Returns -1 if v1 < v2, 0 if equal, 1 if v1 > v2"""
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]

            # Pad shorter version with zeros
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts += [0] * (max_len - len(v1_parts))
            v2_parts += [0] * (max_len - len(v2_parts))

            for i in range(max_len):
                if v1_parts[i] < v2_parts[i]:
                    return -1
                elif v1_parts[i] > v2_parts[i]:
                    return 1
            return 0
        except (ValueError, AttributeError):
            return 0  # Unable to compare

        # Known vulnerability data (simplified for demo - in production use proper CVE databases)
        self.known_vulnerabilities = {
            "pillow": [
                {
                    "versions": ["<10.3.0"],
                    "cve": "CVE-2024-28219",
                    "severity": "HIGH",
                    "description": "Buffer overflow in libwebp"
                }
            ],
            "httpx": [
                {
                    "versions": ["<0.27.0"],
                    "cve": "CVE-2024-37891",
                    "severity": "MEDIUM",
                    "description": "Cookie domain validation bypass"
                }
            ],
            "fastapi": [
                {
                    "versions": ["<0.110.1"],
                    "cve": "CVE-2024-24762",
                    "severity": "HIGH",
                    "description": "Path traversal via filename parameter"
                }
            ]
        }

        # License compatibility matrix
        self.license_compatibility = {
            'MIT': ['MIT', 'BSD', 'Apache-2.0', 'ISC'],
            'Apache-2.0': ['Apache-2.0', 'MIT', 'BSD'],
            'GPL-3.0': ['GPL-3.0', 'GPL-2.0'],
            'BSD-3-Clause': ['BSD-3-Clause', 'MIT', 'Apache-2.0'],
        }

    def parse_requirements(self, filepath: str) -> List[str]:
        """Parse requirements.txt file"""
        dependencies = []
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Extract package name and version
                        if '==' in line:
                            package, version = line.split('==')
                            dependencies.append({'name': package.strip(), 'version': version.strip()})
                        elif '>=' in line:
                            package, version = line.split('>=')
                            dependencies.append({'name': package.strip(), 'version': version.strip()})
                        else:
                            # Handle packages without version specifier
                            dependencies.append({'name': line.strip(), 'version': 'latest'})
        except FileNotFoundError:
            print(f"⚠️  File not found: {filepath}")
        return dependencies

    def get_package_info(self, package_name: str) -> Dict[str, Any]:
        """Fetch package information from PyPI"""
        try:
            url = f"{self.pypi_base_url}/{package_name}/json"
            req = Request(url)
            req.add_header('User-Agent', 'DepAudit/1.0')

            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data
        except URLError as e:
            print(f"⚠️  Could not fetch info for {package_name}: {e}")
            return {}
        except Exception as e:
            print(f"⚠️  Error processing {package_name}: {e}")
            return {}

    def check_vulnerabilities(self, package_name: str, current_version: str) -> List[VulnerabilityInfo]:
        """Check for known vulnerabilities"""
        vulnerabilities = []

        if package_name in self.known_vulnerabilities:
            for vuln in self.known_vulnerabilities[package_name]:
                # Simple version check (in production, use proper version range parsing)
                affected_versions = vuln['versions'][0]  # Simplified
                if '<' in affected_versions:
                    threshold = affected_versions.replace('<', '').strip()
                    try:
                        if self.compare_versions(current_version, threshold) < 0:
                            vulnerabilities.append(VulnerabilityInfo(
                                package=package_name,
                                current_version=current_version,
                                vulnerability_id=vuln['cve'],
                                severity=vuln['severity'],
                                description=vuln['description'],
                                affected_versions=affected_versions,
                                fixed_in=threshold
                            ))
                    except Exception as e:
                        print(f"Version parsing error for {package_name}: {e}")

        return vulnerabilities

    def analyze_dependency(self, dep: Dict[str, str]) -> DependencyInfo:
        """Analyze a single dependency"""
        package_info = self.get_package_info(dep['name'])

        info = DependencyInfo(
            name=dep['name'],
            current_version=dep['version']
        )

        if package_info:
            info.latest_version = package_info.get('info', {}).get('version', 'unknown')
            info.license = package_info.get('info', {}).get('license', 'unknown')
            info.description = package_info.get('info', {}).get('summary', '')[:100]

            # Get release date
            releases = package_info.get('releases', {})
            if dep['version'] in releases and releases[dep['version']]:
                upload_time = releases[dep['version']][0].get('upload_time', '')
                info.last_updated = upload_time[:10] if upload_time else ''

        # Check for vulnerabilities
        info.vulnerabilities = self.check_vulnerabilities(dep['name'], dep['version'])

        return info

    def audit_requirements_file(self, filepath: str, project_name: str) -> Dict[str, Any]:
        """Audit a requirements.txt file"""
        print(f"\n🔍 Auditing {project_name}: {filepath}")

        dependencies = self.parse_requirements(filepath)
        analyzed_deps = []

        total_vulns = 0
        critical_vulns = 0
        high_vulns = 0
        outdated_count = 0
        license_issues = 0

        for dep in dependencies:
            print(f"  📦 Analyzing {dep['name']}...")
            info = self.analyze_dependency(dep)
            analyzed_deps.append(info)

            # Count vulnerabilities
            total_vulns += len(info.vulnerabilities)
            for vuln in info.vulnerabilities:
                if vuln.severity == 'CRITICAL':
                    critical_vulns += 1
                elif vuln.severity == 'HIGH':
                    high_vulns += 1

            # Check if outdated
            if info.latest_version and info.latest_version != 'unknown':
                try:
                    if self.compare_versions(info.current_version, info.latest_version) < 0:
                        outdated_count += 1
                except:
                    pass  # Skip version comparison errors

            # Check license issues
            if info.license in ['GPL-3.0', 'AGPL-3.0', 'unknown']:
                license_issues += 1

        return {
            'project': project_name,
            'file': filepath,
            'total_dependencies': len(dependencies),
            'dependencies': analyzed_deps,
            'summary': {
                'total_vulnerabilities': total_vulns,
                'critical_vulnerabilities': critical_vulns,
                'high_vulnerabilities': high_vulns,
                'outdated_packages': outdated_count,
                'license_issues': license_issues,
                'security_score': max(0, 100 - (critical_vulns * 25) - (high_vulns * 10) - (total_vulns * 5))
            }
        }

    def generate_report(self, audits: List[Dict[str, Any]]) -> str:
        """Generate comprehensive audit report"""
        report = []
        report.append("# 🔒 Dependency Security Audit Report")
        report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Executive Summary
        total_deps = sum(audit['total_dependencies'] for audit in audits)
        total_vulns = sum(audit['summary']['total_vulnerabilities'] for audit in audits)
        critical_vulns = sum(audit['summary']['critical_vulnerabilities'] for audit in audits)
        high_vulns = sum(audit['summary']['high_vulnerabilities'] for audit in audits)

        report.append("## 📊 Executive Summary")
        report.append("")
        report.append(f"- **Total Dependencies**: {total_deps}")
        report.append(f"- **Security Vulnerabilities**: {total_vulns}")
        report.append(f"- **Critical Vulnerabilities**: {critical_vulns}")
        report.append(f"- **High Vulnerabilities**: {high_vulns}")

        if critical_vulns > 0:
            report.append(f"- **Risk Level**: 🚨 **CRITICAL** - Immediate action required")
        elif high_vulns > 0:
            report.append(f"- **Risk Level**: ⚠️ **HIGH** - Update soon")
        elif total_vulns > 0:
            report.append(f"- **Risk Level**: 🟡 **MEDIUM** - Monitor and plan updates")
        else:
            report.append(f"- **Risk Level**: ✅ **LOW** - No known vulnerabilities")

        report.append("")

        # Per-project analysis
        for audit in audits:
            report.append(f"## 📦 {audit['project']}")
            report.append("")
            report.append(f"**File**: `{audit['file']}`")
            report.append(f"**Dependencies**: {audit['total_dependencies']}")
            report.append(f"**Security Score**: {audit['summary']['security_score']}/100")
            report.append("")

            # Vulnerabilities
            if audit['summary']['total_vulnerabilities'] > 0:
                report.append("### 🚨 Security Vulnerabilities")
                report.append("")
                report.append("| Package | Current | Vulnerability | Severity | Description |")
                report.append("|---------|---------|--------------|----------|-------------|")

                for dep in audit['dependencies']:
                    for vuln in dep.vulnerabilities:
                        report.append(f"| {dep.name} | {dep.current_version} | {vuln.vulnerability_id} | {vuln.severity} | {vuln.description} |")
                report.append("")

            # Outdated packages
            outdated_deps = [dep for dep in audit['dependencies']
                           if dep.latest_version and dep.latest_version != 'unknown' and dep.latest_version != dep.current_version]

            if outdated_deps:
                report.append("### 📅 Outdated Dependencies")
                report.append("")
                report.append("| Package | Current | Latest | Behind |")
                report.append("|---------|---------|--------|--------|")

                for dep in outdated_deps:
                    try:
                        current_parts = dep.current_version.split('.')
                        latest_parts = dep.latest_version.split('.')
                        if len(current_parts) >= 3 and len(latest_parts) >= 3:
                            if int(latest_parts[0]) > int(current_parts[0]):
                                status = "🔴 Major"
                            elif int(latest_parts[1]) > int(current_parts[1]):
                                status = "🟡 Minor"
                            else:
                                status = "🟢 Patch"
                        else:
                            status = "❓ Unknown"
                    except:
                        status = "❓ Unknown"

                    report.append(f"| {dep.name} | {dep.current_version} | {dep.latest_version} | {status} |")
                report.append("")

            # License analysis
            license_summary = {}
            for dep in audit['dependencies']:
                lic = dep.license if dep.license else 'unknown'
                license_summary[lic] = license_summary.get(lic, 0) + 1

            if license_summary:
                report.append("### 📄 License Summary")
                report.append("")
                for license_type, count in sorted(license_summary.items(), key=lambda x: x[1], reverse=True):
                    emoji = "⚠️" if license_type in ['GPL-3.0', 'AGPL-3.0', 'unknown'] else "✅"
                    report.append(f"- {emoji} **{license_type}**: {count} packages")
                report.append("")

        # Recommendations
        report.append("## 🔧 Recommended Actions")
        report.append("")

        if critical_vulns > 0:
            report.append("### 🚨 Critical Actions (Do Immediately)")
            report.append("")
            for audit in audits:
                for dep in audit['dependencies']:
                    for vuln in dep.vulnerabilities:
                        if vuln.severity == 'CRITICAL':
                            report.append(f"1. **Update {dep.name}** from {dep.current_version} to {vuln.fixed_in}")
                            report.append(f"   - Vulnerability: {vuln.vulnerability_id}")
                            report.append(f"   - Issue: {vuln.description}")
                            report.append("")

        if high_vulns > 0:
            report.append("### ⚠️ High Priority Actions (This Week)")
            report.append("")
            for audit in audits:
                for dep in audit['dependencies']:
                    for vuln in dep.vulnerabilities:
                        if vuln.severity == 'HIGH':
                            report.append(f"1. **Update {dep.name}** from {dep.current_version} to {vuln.fixed_in}")
                            report.append(f"   - Vulnerability: {vuln.vulnerability_id}")
                            report.append(f"   - Issue: {vuln.description}")
                            report.append("")

        # Update commands
        report.append("## 🛠️ Update Commands")
        report.append("")
        report.append("### Backend Dependencies")
        report.append("```bash")
        report.append("cd backend")
        for audit in audits:
            if 'backend' in audit['file']:
                for dep in audit['dependencies']:
                    for vuln in dep.vulnerabilities:
                        if vuln.fixed_in:
                            report.append(f"pip install {dep.name}=={vuln.fixed_in}")
        report.append("pip freeze > requirements.txt")
        report.append("```")
        report.append("")

        report.append("### Frontend Dependencies")
        report.append("```bash")
        report.append("cd frontend")
        for audit in audits:
            if 'frontend' in audit['file']:
                for dep in audit['dependencies']:
                    for vuln in dep.vulnerabilities:
                        if vuln.fixed_in:
                            report.append(f"pip install {dep.name}=={vuln.fixed_in}")
        report.append("pip freeze > requirements.txt")
        report.append("```")
        report.append("")

        return "\n".join(report)

def main():
    auditor = DependencyAuditor()

    # Audit both requirements files
    audits = []

    for req_file in ['./backend/requirements.txt', './frontend/requirements.txt']:
        try:
            project_name = req_file.split('/')[1].title()
            audit_result = auditor.audit_requirements_file(req_file, project_name)
            audits.append(audit_result)
        except Exception as e:
            print(f"Error auditing {req_file}: {e}")

    # Generate report
    if audits:
        report = auditor.generate_report(audits)

        # Save report
        with open('dependency_audit_report.md', 'w') as f:
            f.write(report)

        print("\n" + "="*60)
        print("📋 DEPENDENCY AUDIT COMPLETE")
        print("="*60)
        print(f"Report saved to: dependency_audit_report.md")
        print("\nKey findings:")

        total_vulns = sum(audit['summary']['total_vulnerabilities'] for audit in audits)
        if total_vulns > 0:
            print(f"🚨 Found {total_vulns} security vulnerabilities")
        else:
            print("✅ No known security vulnerabilities found")

        print("\n" + "="*60)
    else:
        print("❌ No dependency files could be audited")

if __name__ == "__main__":
    main()