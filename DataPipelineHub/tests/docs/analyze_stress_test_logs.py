#!/usr/bin/env python3
"""
Stress Test Log Analyzer
=========================
Analyzes stress test log files to generate detailed reports and visualizations.
"""

import re
import sys
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple


class LogAnalyzer:
    """Analyzes stress test log files"""
    
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.lines = []
        self.upload_times = []
        self.upload_successes = 0
        self.upload_failures = 0
        self.task_statuses = defaultdict(int)
        self.errors = defaultdict(int)
        self.test_start_time = None
        self.test_end_time = None
        
    def load_log(self):
        """Load log file"""
        try:
            with open(self.log_file, 'r') as f:
                self.lines = f.readlines()
            print(f"✓ Loaded {len(self.lines)} lines from {self.log_file}")
        except Exception as e:
            print(f"✗ Error loading log file: {e}")
            sys.exit(1)
    
    def parse_timestamps(self):
        """Extract test start and end times"""
        timestamp_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})'
        
        for line in self.lines:
            if "Test started at:" in line:
                match = re.search(r'Test started at: ([\d\-T:]+)', line)
                if match:
                    self.test_start_time = match.group(1)
            elif "Test ended at:" in line:
                match = re.search(r'Test ended at: ([\d\-T:]+)', line)
                if match:
                    self.test_end_time = match.group(1)
        
        # If not found in logs, use first and last timestamp
        if not self.test_start_time:
            match = re.search(timestamp_pattern, self.lines[0])
            if match:
                self.test_start_time = match.group(1)
        
        if not self.test_end_time:
            match = re.search(timestamp_pattern, self.lines[-1])
            if match:
                self.test_end_time = match.group(1)
    
    def parse_uploads(self):
        """Extract upload statistics"""
        success_pattern = r'✓ Document \d+ \(.+?\) uploaded successfully in ([\d.]+)s'
        failure_pattern = r'✗ Document \d+ \(.+?\) upload (failed|error|timeout)'
        
        for line in self.lines:
            # Check for successful upload
            match = re.search(success_pattern, line)
            if match:
                self.upload_successes += 1
                self.upload_times.append(float(match.group(1)))
            
            # Check for failed upload
            if re.search(failure_pattern, line):
                self.upload_failures += 1
                
                # Extract error type
                if "timeout" in line.lower():
                    self.errors["Timeout"] += 1
                elif "HTTP" in line:
                    http_match = re.search(r'HTTP (\d+)', line)
                    if http_match:
                        self.errors[f"HTTP {http_match.group(1)}"] += 1
                else:
                    self.errors["Unknown"] += 1
    
    def parse_tasks(self):
        """Extract Celery task statistics"""
        success_pattern = r'✓ Task .+ completed successfully'
        failure_pattern = r'✗ Task .+ failed'
        
        for line in self.lines:
            if re.search(success_pattern, line):
                self.task_statuses['SUCCESS'] += 1
            elif re.search(failure_pattern, line):
                self.task_statuses['FAILURE'] += 1
    
    def parse_summary(self) -> Dict:
        """Extract final summary if available"""
        summary = {}
        in_summary = False
        
        for line in self.lines:
            if "UPLOAD PHASE SUMMARY" in line:
                in_summary = "upload"
            elif "EMBEDDING PHASE SUMMARY" in line:
                in_summary = "embedding"
            elif "OVERALL ASSESSMENT" in line:
                in_summary = "assessment"
            elif in_summary:
                # Parse summary values
                if "Total upload attempts:" in line:
                    match = re.search(r': (\d+)', line)
                    if match:
                        summary['total_uploads'] = int(match.group(1))
                elif "Successful uploads:" in line:
                    match = re.search(r': (\d+)', line)
                    if match:
                        summary['successful_uploads'] = int(match.group(1))
                elif "Failed uploads:" in line:
                    match = re.search(r': (\d+)', line)
                    if match:
                        summary['failed_uploads'] = int(match.group(1))
                elif "Success rate:" in line:
                    match = re.search(r': ([\d.]+)%', line)
                    if match:
                        summary['success_rate'] = float(match.group(1))
                elif "Average upload time:" in line:
                    match = re.search(r': ([\d.]+)s', line)
                    if match:
                        summary['avg_upload_time'] = float(match.group(1))
                elif "Successful tasks:" in line:
                    match = re.search(r': (\d+)', line)
                    if match:
                        summary['successful_tasks'] = int(match.group(1))
                elif "Failed tasks:" in line:
                    match = re.search(r': (\d+)', line)
                    if match:
                        summary['failed_tasks'] = int(match.group(1))
        
        return summary
    
    def calculate_statistics(self) -> Dict:
        """Calculate detailed statistics"""
        stats = {}
        
        # Upload statistics
        if self.upload_times:
            stats['upload_count'] = len(self.upload_times)
            stats['upload_avg'] = sum(self.upload_times) / len(self.upload_times)
            stats['upload_min'] = min(self.upload_times)
            stats['upload_max'] = max(self.upload_times)
            stats['upload_median'] = sorted(self.upload_times)[len(self.upload_times) // 2]
            
            # Calculate percentiles
            sorted_times = sorted(self.upload_times)
            stats['upload_p95'] = sorted_times[int(len(sorted_times) * 0.95)]
            stats['upload_p99'] = sorted_times[int(len(sorted_times) * 0.99)]
        
        stats['upload_successes'] = self.upload_successes
        stats['upload_failures'] = self.upload_failures
        stats['upload_total'] = self.upload_successes + self.upload_failures
        
        if stats['upload_total'] > 0:
            stats['upload_success_rate'] = (self.upload_successes / stats['upload_total']) * 100
        
        # Task statistics
        stats['task_statuses'] = dict(self.task_statuses)
        stats['task_total'] = sum(self.task_statuses.values())
        
        # Error statistics
        stats['errors'] = dict(self.errors)
        stats['error_total'] = sum(self.errors.values())
        
        return stats
    
    def print_report(self):
        """Print comprehensive analysis report"""
        print("\n" + "="*80)
        print("STRESS TEST LOG ANALYSIS REPORT")
        print("="*80)
        print(f"\nLog File: {self.log_file}")
        
        if self.test_start_time and self.test_end_time:
            print(f"Test Start: {self.test_start_time}")
            print(f"Test End:   {self.test_end_time}")
        
        # Get statistics
        stats = self.calculate_statistics()
        summary = self.parse_summary()
        
        # Upload Analysis
        print("\n" + "-"*80)
        print("UPLOAD ANALYSIS")
        print("-"*80)
        print(f"Total Uploads:     {stats['upload_total']}")
        print(f"Successful:        {stats['upload_successes']} ({stats.get('upload_success_rate', 0):.2f}%)")
        print(f"Failed:            {stats['upload_failures']}")
        
        if self.upload_times:
            print(f"\nUpload Time Statistics:")
            print(f"  Average:         {stats['upload_avg']:.2f}s")
            print(f"  Median:          {stats['upload_median']:.2f}s")
            print(f"  Min:             {stats['upload_min']:.2f}s")
            print(f"  Max:             {stats['upload_max']:.2f}s")
            print(f"  95th percentile: {stats['upload_p95']:.2f}s")
            print(f"  99th percentile: {stats['upload_p99']:.2f}s")
        
        # Error Analysis
        if stats['error_total'] > 0:
            print(f"\nError Breakdown:")
            for error_type, count in sorted(stats['errors'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {error_type}: {count}")
        
        # Task Analysis
        print("\n" + "-"*80)
        print("CELERY TASK ANALYSIS")
        print("-"*80)
        print(f"Total Tasks:       {stats['task_total']}")
        
        if stats['task_statuses']:
            print(f"\nTask Status Breakdown:")
            for status, count in sorted(stats['task_statuses'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {status}: {count}")
        
        # Summary from logs (if available)
        if summary:
            print("\n" + "-"*80)
            print("TEST SUMMARY (from logs)")
            print("-"*80)
            for key, value in summary.items():
                formatted_key = key.replace('_', ' ').title()
                if isinstance(value, float):
                    print(f"{formatted_key}: {value:.2f}")
                else:
                    print(f"{formatted_key}: {value}")
        
        # Overall Assessment
        print("\n" + "-"*80)
        print("OVERALL ASSESSMENT")
        print("-"*80)
        
        upload_ok = stats.get('upload_success_rate', 0) >= 95
        tasks_ok = self.task_statuses.get('FAILURE', 0) == 0 and self.task_statuses.get('SUCCESS', 0) > 0
        
        if upload_ok and tasks_ok:
            print("✓ TEST RESULT: PASSED")
            print("  - Upload success rate meets threshold (≥95%)")
            print("  - No task failures detected")
        else:
            print("✗ TEST RESULT: FAILED")
            if not upload_ok:
                print(f"  - Upload success rate below threshold: {stats.get('upload_success_rate', 0):.2f}% < 95%")
            if not tasks_ok:
                print(f"  - Task failures detected: {self.task_statuses.get('FAILURE', 0)}")
        
        print("\n" + "="*80)
    
    def export_json(self, output_file: str):
        """Export analysis to JSON"""
        stats = self.calculate_statistics()
        summary = self.parse_summary()
        
        data = {
            'log_file': self.log_file,
            'test_start_time': self.test_start_time,
            'test_end_time': self.test_end_time,
            'statistics': stats,
            'summary': summary,
            'upload_times': self.upload_times
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n✓ Analysis exported to {output_file}")
    
    def analyze(self):
        """Run complete analysis"""
        print("Analyzing stress test log...")
        self.load_log()
        self.parse_timestamps()
        self.parse_uploads()
        self.parse_tasks()
        self.print_report()


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python analyze_stress_test_logs.py <log_file> [--export-json output.json]")
        print("\nExample:")
        print("  python analyze_stress_test_logs.py stress_test_20241110_153045.log")
        print("  python analyze_stress_test_logs.py stress_test_20241110_153045.log --export-json analysis.json")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    if not Path(log_file).exists():
        print(f"✗ Log file not found: {log_file}")
        sys.exit(1)
    
    analyzer = LogAnalyzer(log_file)
    analyzer.analyze()
    
    # Check for JSON export option
    if len(sys.argv) >= 4 and sys.argv[2] == '--export-json':
        output_file = sys.argv[3]
        analyzer.export_json(output_file)


if __name__ == "__main__":
    main()

