#!/usr/bin/env python3
"""
Bundle Size and Performance Impact Analysis for Python Dependencies
"""
import json
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any
import tempfile
from datetime import datetime

@dataclass
class PackageAnalysis:
    name: str
    version: str
    install_size: int = 0
    import_time: float = 0.0
    memory_usage: int = 0
    dependencies: List[str] = None
    performance_impact: str = "Unknown"

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

class BundleAnalyzer:
    def __init__(self):
        self.heavy_packages = {
            'pandas': {'typical_size': '50MB', 'impact': 'HIGH', 'alternatives': ['polars', 'dask']},
            'numpy': {'typical_size': '20MB', 'impact': 'MEDIUM', 'alternatives': ['jax']},
            'tensorflow': {'typical_size': '500MB', 'impact': 'CRITICAL', 'alternatives': ['pytorch', 'jax']},
            'pytorch': {'typical_size': '800MB', 'impact': 'CRITICAL', 'alternatives': ['tensorflow', 'jax']},
            'scipy': {'typical_size': '30MB', 'impact': 'MEDIUM', 'alternatives': ['numpy']},
            'scikit-learn': {'typical_size': '40MB', 'impact': 'MEDIUM', 'alternatives': ['xgboost']},
            'matplotlib': {'typical_size': '35MB', 'impact': 'MEDIUM', 'alternatives': ['plotly', 'seaborn']},
            'plotly': {'typical_size': '25MB', 'impact': 'MEDIUM', 'alternatives': ['matplotlib', 'bokeh']},
            'streamlit': {'typical_size': '15MB', 'impact': 'MEDIUM', 'alternatives': ['gradio', 'dash']},
            'langchain': {'typical_size': '10MB', 'impact': 'MEDIUM', 'alternatives': ['llama-index']},
            'chromadb': {'typical_size': '8MB', 'impact': 'LOW', 'alternatives': ['faiss', 'pinecone']},
            'pillow': {'typical_size': '5MB', 'impact': 'LOW', 'alternatives': ['opencv-python']},
            'sqlalchemy': {'typical_size': '3MB', 'impact': 'LOW', 'alternatives': ['sqlite3', 'psycopg2']},
            'fastapi': {'typical_size': '2MB', 'impact': 'LOW', 'alternatives': ['flask', 'django']}
        }

    def get_package_size(self, package_name: str, version: str = None) -> int:
        """Estimate package installation size"""
        # For demonstration, we'll use typical sizes
        # In production, this would use actual pip show or wheel analysis
        if package_name in self.heavy_packages:
            size_str = self.heavy_packages[package_name]['typical_size']
            if 'MB' in size_str:
                return int(float(size_str.replace('MB', '')) * 1024 * 1024)
            elif 'KB' in size_str:
                return int(float(size_str.replace('KB', '')) * 1024)

        # Default estimates based on package type
        if any(keyword in package_name.lower() for keyword in ['ml', 'ai', 'torch', 'tensor']):
            return 50 * 1024 * 1024  # 50MB for ML packages
        elif any(keyword in package_name.lower() for keyword in ['data', 'pandas', 'numpy']):
            return 25 * 1024 * 1024  # 25MB for data packages
        elif any(keyword in package_name.lower() for keyword in ['web', 'http', 'api']):
            return 5 * 1024 * 1024   # 5MB for web packages
        else:
            return 1 * 1024 * 1024   # 1MB default

    def measure_import_time(self, package_name: str) -> float:
        """Measure package import time"""
        try:
            import time
            # Create a subprocess to measure import time
            code = f"""
import time
start = time.time()
try:
    import {package_name}
    end = time.time()
    print(end - start)
except ImportError:
    print(-1)
"""

            result = subprocess.run([sys.executable, '-c', code],
                                  capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return float(result.stdout.strip())
            else:
                return -1  # Import failed
        except Exception:
            return -1

    def analyze_package(self, package_name: str, version: str) -> PackageAnalysis:
        """Analyze a single package for size and performance"""
        print(f"  📊 Analyzing {package_name}...")

        analysis = PackageAnalysis(name=package_name, version=version)

        # Get estimated size
        analysis.install_size = self.get_package_size(package_name, version)

        # Measure import time (simplified for demo)
        # analysis.import_time = self.measure_import_time(package_name)

        # Determine performance impact
        if package_name in self.heavy_packages:
            impact_info = self.heavy_packages[package_name]
            analysis.performance_impact = impact_info['impact']
        elif analysis.install_size > 50 * 1024 * 1024:  # > 50MB
            analysis.performance_impact = "HIGH"
        elif analysis.install_size > 10 * 1024 * 1024:  # > 10MB
            analysis.performance_impact = "MEDIUM"
        else:
            analysis.performance_impact = "LOW"

        return analysis

    def parse_requirements(self, filepath: str) -> List[Dict[str, str]]:
        """Parse requirements.txt file"""
        packages = []
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '==' in line:
                            name, version = line.split('==', 1)
                            # Handle extras like uvicorn[standard]
                            if '[' in name:
                                name = name.split('[')[0]
                            packages.append({'name': name.strip(), 'version': version.strip()})
        except FileNotFoundError:
            print(f"❌ File not found: {filepath}")
        return packages

    def analyze_project(self, filepath: str, project_name: str) -> Dict[str, Any]:
        """Analyze entire project dependencies"""
        print(f"\n📦 Bundle Analysis: {project_name}")

        packages = self.parse_requirements(filepath)
        analyzed = []

        total_size = 0
        high_impact_count = 0
        medium_impact_count = 0

        for pkg in packages:
            analysis = self.analyze_package(pkg['name'], pkg['version'])
            analyzed.append(analysis)

            total_size += analysis.install_size
            if analysis.performance_impact == "HIGH":
                high_impact_count += 1
            elif analysis.performance_impact == "MEDIUM":
                medium_impact_count += 1

        return {
            'project': project_name,
            'file': filepath,
            'packages': analyzed,
            'summary': {
                'total_packages': len(packages),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'high_impact_packages': high_impact_count,
                'medium_impact_packages': medium_impact_count,
                'average_size_mb': round(total_size / len(packages) / (1024 * 1024), 2) if packages else 0
            }
        }

    def generate_bundle_report(self, analyses: List[Dict[str, Any]]) -> str:
        """Generate comprehensive bundle analysis report"""
        report = []

        # Header
        report.append("# 📊 Bundle Size and Performance Analysis")
        report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Executive Summary
        total_size = sum(a['summary']['total_size_mb'] for a in analyses)
        total_packages = sum(a['summary']['total_packages'] for a in analyses)

        report.append("## 📈 Executive Summary")
        report.append("")
        report.append(f"- **Total Dependencies**: {total_packages}")
        report.append(f"- **Combined Bundle Size**: {total_size:.1f} MB")
        report.append(f"- **Average Package Size**: {total_size/total_packages if total_packages > 0 else 0:.1f} MB")

        # Size categories
        if total_size > 200:
            size_category = "🔴 **LARGE** - Consider optimization"
        elif total_size > 100:
            size_category = "🟡 **MEDIUM** - Monitor growth"
        else:
            size_category = "✅ **REASONABLE** - Within normal limits"

        report.append(f"- **Bundle Size Assessment**: {size_category}")
        report.append("")

        # Per-project analysis
        for analysis in analyses:
            report.append(f"## 📦 {analysis['project']} Bundle Analysis")
            report.append("")
            report.append(f"- **Size**: {analysis['summary']['total_size_mb']:.1f} MB")
            report.append(f"- **Dependencies**: {analysis['summary']['total_packages']}")
            report.append(f"- **High Impact**: {analysis['summary']['high_impact_packages']} packages")
            report.append(f"- **Medium Impact**: {analysis['summary']['medium_impact_packages']} packages")
            report.append("")

            # Package breakdown
            packages = sorted(analysis['packages'],
                            key=lambda x: x.install_size, reverse=True)

            report.append("### 📊 Package Size Breakdown")
            report.append("")
            report.append("| Package | Version | Size (MB) | Impact | Notes |")
            report.append("|---------|---------|-----------|--------|-------|")

            for pkg in packages:
                size_mb = pkg.install_size / (1024 * 1024)
                impact_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "✅"}.get(pkg.performance_impact, "❓")

                notes = ""
                if pkg.name in self.heavy_packages:
                    alternatives = self.heavy_packages[pkg.name].get('alternatives', [])
                    if alternatives:
                        notes = f"Alt: {', '.join(alternatives[:2])}"

                report.append(f"| {pkg.name} | {pkg.version} | {size_mb:.1f} | {impact_emoji} {pkg.performance_impact} | {notes} |")

            report.append("")

            # Optimization recommendations
            heavy_packages = [p for p in packages if p.performance_impact in ["HIGH", "MEDIUM"]]
            if heavy_packages:
                report.append("### 🚀 Optimization Recommendations")
                report.append("")

                for pkg in heavy_packages[:5]:  # Top 5 heaviest
                    if pkg.name in self.heavy_packages:
                        info = self.heavy_packages[pkg.name]
                        report.append(f"**{pkg.name}** ({pkg.install_size / (1024*1024):.1f} MB)")

                        alternatives = info.get('alternatives', [])
                        if alternatives:
                            report.append(f"- Consider alternatives: {', '.join(alternatives)}")

                        if pkg.performance_impact == "HIGH":
                            report.append(f"- High performance impact - evaluate necessity")

                        report.append("")

        # Performance optimization strategies
        report.append("## ⚡ Performance Optimization Strategies")
        report.append("")
        report.append("### Bundle Size Reduction")
        report.append("1. **Lazy Loading**: Import heavy packages only when needed")
        report.append("2. **Optional Dependencies**: Make heavy packages optional")
        report.append("3. **Alternative Packages**: Use lighter alternatives where possible")
        report.append("4. **Tree Shaking**: Remove unused code/features")
        report.append("")

        report.append("### Runtime Performance")
        report.append("1. **Import Optimization**: Delay imports until runtime")
        report.append("2. **Caching**: Cache heavy computation results")
        report.append("3. **Async Operations**: Use async for I/O heavy operations")
        report.append("4. **Memory Management**: Monitor memory usage patterns")
        report.append("")

        # Docker optimization
        report.append("### 🐳 Docker Image Optimization")
        report.append("```dockerfile")
        report.append("# Multi-stage build to reduce final image size")
        report.append("FROM python:3.11-slim as builder")
        report.append("")
        report.append("# Install only production dependencies")
        report.append("COPY requirements.txt .")
        report.append("RUN pip install --no-cache-dir -r requirements.txt")
        report.append("")
        report.append("# Use distroless for smaller final image")
        report.append("FROM gcr.io/distroless/python3-debian11")
        report.append("COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages")
        report.append("```")
        report.append("")

        # CI/CD recommendations
        report.append("## 🔄 Continuous Monitoring")
        report.append("```yaml")
        report.append("# GitHub Actions workflow for bundle size monitoring")
        report.append("name: Bundle Size Analysis")
        report.append("")
        report.append("on: [push, pull_request]")
        report.append("")
        report.append("jobs:")
        report.append("  bundle-analysis:")
        report.append("    runs-on: ubuntu-latest")
        report.append("    steps:")
        report.append("      - uses: actions/checkout@v3")
        report.append("      - name: Analyze Dependencies")
        report.append("        run: python bundle_analysis.py")
        report.append("      - name: Comment PR")
        report.append("        if: github.event_name == 'pull_request'")
        report.append("        run: |")
        report.append("          echo 'Bundle size: X MB' >> $GITHUB_STEP_SUMMARY")
        report.append("```")
        report.append("")

        return "\n".join(report)

def main():
    print("📊 Bundle Size and Performance Analysis")
    print("=" * 50)

    analyzer = BundleAnalyzer()
    analyses = []

    # Analyze both projects
    requirements_files = [
        ('./backend/requirements.txt', 'Backend'),
        ('./frontend/requirements.txt', 'Frontend')
    ]

    for file_path, project_name in requirements_files:
        try:
            analysis = analyzer.analyze_project(file_path, project_name)
            analyses.append(analysis)
        except Exception as e:
            print(f"❌ Error analyzing {file_path}: {e}")

    if analyses:
        # Generate report
        report = analyzer.generate_bundle_report(analyses)

        report_file = 'bundle_analysis_report.md'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print("\n" + "=" * 50)
        print("📊 BUNDLE ANALYSIS COMPLETE")
        print("=" * 50)
        print(f"📊 Report saved to: {report_file}")

        # Print summary
        total_size = sum(a['summary']['total_size_mb'] for a in analyses)
        total_packages = sum(a['summary']['total_packages'] for a in analyses)

        print(f"\n📦 Bundle Summary:")
        print(f"  📊 Total Size: {total_size:.1f} MB")
        print(f"  📈 Packages: {total_packages}")
        print(f"  📉 Average: {total_size/total_packages if total_packages > 0 else 0:.1f} MB per package")

        # Size recommendations
        if total_size > 200:
            print("  🔴 Large bundle - consider optimization")
        elif total_size > 100:
            print("  🟡 Medium bundle - monitor growth")
        else:
            print("  ✅ Reasonable bundle size")
    else:
        print("❌ No files could be analyzed")

if __name__ == "__main__":
    main()