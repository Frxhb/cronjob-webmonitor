#!/usr/bin/env python3
import subprocess
import json
import time
import tempfile
import os
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import re

class CronPreview:
    @staticmethod
    def parse_cron(expression):
        """Enhanced cron parser with detailed explanations"""
        try:
            parts = expression.strip().split()
            if len(parts) != 5:
                return {
                    'valid': False,
                    'description': 'Invalid cron expression - must have 5 parts',
                    'next_runs': [],
                    'explanation': 'Cron format: minute hour day month weekday'
                }
            
            minute, hour, day, month, weekday = parts
            
            # Generate detailed explanation
            explanation_parts = []
            
            # Minute explanation
            if minute == '*':
                explanation_parts.append('every minute')
            elif '/' in minute:
                if minute.startswith('*/'):
                    explanation_parts.append(f'every {minute[2:]} minutes')
                else:
                    explanation_parts.append(f'every {minute.split("/")[1]} minutes starting at minute {minute.split("/")[0]}')
            elif ',' in minute:
                explanation_parts.append(f'at minutes {minute}')
            elif '-' in minute:
                start, end = minute.split('-')
                explanation_parts.append(f'from minute {start} to {end}')
            else:
                explanation_parts.append(f'at minute {minute}')
            
            # Hour explanation
            if hour != '*':
                if '/' in hour:
                    if hour.startswith('*/'):
                        explanation_parts.append(f'every {hour[2:]} hours')
                    else:
                        explanation_parts.append(f'every {hour.split("/")[1]} hours starting at hour {hour.split("/")[0]}')
                elif ',' in hour:
                    explanation_parts.append(f'at hours {hour}')
                elif '-' in hour:
                    start, end = hour.split('-')
                    explanation_parts.append(f'from hour {start} to {end}')
                else:
                    explanation_parts.append(f'at {hour}:XX')
            
            # Day explanation
            if day != '*':
                if '/' in day:
                    explanation_parts.append(f'every {day.split("/")[1]} days')
                elif ',' in day:
                    explanation_parts.append(f'on days {day}')
                elif '-' in day:
                    start, end = day.split('-')
                    explanation_parts.append(f'from day {start} to {end}')
                else:
                    explanation_parts.append(f'on day {day}')
            
            # Month explanation
            if month != '*':
                months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                if month.isdigit() and 1 <= int(month) <= 12:
                    explanation_parts.append(f'in {months[int(month)-1]}')
                elif ',' in month:
                    month_names = [months[int(m)-1] for m in month.split(',') if m.isdigit() and 1 <= int(m) <= 12]
                    explanation_parts.append(f'in {", ".join(month_names)}')
            
            # Weekday explanation
            if weekday != '*':
                days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
                if weekday.isdigit() and 0 <= int(weekday) <= 6:
                    explanation_parts.append(f'on {days[int(weekday)]}')
                elif ',' in weekday:
                    day_names = [days[int(d)] for d in weekday.split(',') if d.isdigit() and 0 <= int(d) <= 6]
                    explanation_parts.append(f'on {", ".join(day_names)}')
            
            # Generate human-readable description
            description = CronPreview.get_common_patterns(expression) or " ".join(explanation_parts).capitalize()
            
            # Calculate next runs
            next_runs = CronPreview.calculate_next_runs(parts)
            
            return {
                'valid': True,
                'description': description,
                'next_runs': next_runs,
                'explanation': " ".join(explanation_parts).capitalize(),
                'breakdown': {
                    'minute': CronPreview.explain_field(minute, 'minute', 0, 59),
                    'hour': CronPreview.explain_field(hour, 'hour', 0, 23),
                    'day': CronPreview.explain_field(day, 'day of month', 1, 31),
                    'month': CronPreview.explain_field(month, 'month', 1, 12),
                    'weekday': CronPreview.explain_field(weekday, 'day of week', 0, 6)
                }
            }
            
        except Exception as e:
            return {
                'valid': False,
                'description': 'Error parsing cron expression',
                'next_runs': [],
                'explanation': str(e)
            }
    
    @staticmethod
    def get_common_patterns(expression):
        """Recognize common cron patterns"""
        patterns = {
            '* * * * *': 'Every minute',
            '0 * * * *': 'Every hour',
            '0 0 * * *': 'Daily at midnight',
            '0 12 * * *': 'Daily at noon',
            '0 9 * * 1': 'Every Monday at 9 AM',
            '0 0 1 * *': 'First day of every month',
            '0 0 1 1 *': 'Every New Year (January 1st)',
            '*/5 * * * *': 'Every 5 minutes',
            '*/15 * * * *': 'Every 15 minutes',
            '*/30 * * * *': 'Every 30 minutes',
            '0 */6 * * *': 'Every 6 hours',
            '0 2 * * *': 'Daily at 2 AM',
            '0 0 * * 0': 'Every Sunday at midnight',
            '0 0 * * 1-5': 'Weekdays at midnight',
            '30 2 * * 1-5': 'Weekdays at 2:30 AM'
        }
        return patterns.get(expression)
    
    @staticmethod
    def explain_field(field, field_name, min_val, max_val):
        """Explain individual cron field"""
        if field == '*':
            return f'Any {field_name}'
        elif '/' in field:
            if field.startswith('*/'):
                return f'Every {field[2:]} {field_name}s'
            else:
                parts = field.split('/')
                return f'Every {parts[1]} {field_name}s starting from {parts[0]}'
        elif ',' in field:
            return f'{field_name}s: {field}'
        elif '-' in field:
            start, end = field.split('-')
            return f'{field_name}s from {start} to {end}'
        else:
            return f'{field_name} {field}'
    
    @staticmethod
    def calculate_next_runs(parts, count=5):
        """Calculate next run times (simplified implementation)"""
        minute, hour, day, month, weekday = parts
        now = datetime.now()
        next_runs = []
        
        try:
            # Simple calculation for common patterns
            if parts == ['*', '*', '*', '*', '*']:
                # Every minute
                for i in range(count):
                    next_run = now + timedelta(minutes=i+1)
                    next_runs.append(next_run.strftime("%Y-%m-%d %H:%M"))
            
            elif minute.startswith('*/') and hour == '*':
                # Every X minutes
                interval = int(minute[2:])
                for i in range(count):
                    next_run = now + timedelta(minutes=interval * (i+1))
                    next_runs.append(next_run.strftime("%Y-%m-%d %H:%M"))
            
            elif minute.isdigit() and hour.isdigit():
                # Specific time daily
                target_hour = int(hour)
                target_minute = int(minute)
                
                next_run = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
                for i in range(count):
                    if next_run <= now:
                        next_run += timedelta(days=1)
                    next_runs.append(next_run.strftime("%Y-%m-%d %H:%M"))
                    next_run += timedelta(days=1)
            
            elif minute == '0' and hour == '*':
                # Every hour
                next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                for i in range(count):
                    next_runs.append(next_run.strftime("%Y-%m-%d %H:%M"))
                    next_run += timedelta(hours=1)
            
            else:
                # Generic fallback
                for i in range(count):
                    next_run = now + timedelta(hours=i+1)
                    next_runs.append(next_run.strftime("%Y-%m-%d %H:%M"))
            
        except Exception:
            pass
        
        return next_runs[:count]

class CronMonitorServer(BaseHTTPRequestHandler):
    def _send_headers(self, status=200, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()

    def do_GET(self):
        if self.path == '/':
            self._send_headers(200, 'text/html')
            self.wfile.write(self.get_dashboard_html().encode())
        
        elif self.path == '/api/jobs':
            self._send_headers(200)
            jobs = self.get_cron_jobs()
            self.wfile.write(json.dumps(jobs).encode())
        
        elif self.path == '/api/activity':
            self._send_headers(200)
            activity = self.get_cron_activity()
            self.wfile.write(json.dumps(activity).encode())
        
        elif self.path.startswith('/api/preview/'):
            expression = self.path.split('/')[-1].replace('%20', ' ').replace('%2A', '*')
            self._send_headers(200)
            preview = CronPreview.parse_cron(expression)
            self.wfile.write(json.dumps(preview).encode())
        
        else:
            self._send_headers(404)

    def do_POST(self):
        if self.path == '/api/jobs/add':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode()
            data = json.loads(post_data)
            
            success = self.add_cron_job(data['schedule'], data['command'], data.get('comment', ''))
            
            self._send_headers(200 if success else 500)
            self.wfile.write(json.dumps({'success': success}).encode())

    def do_DELETE(self):
        if self.path.startswith('/api/jobs/'):
            job_index = int(self.path.split('/')[-1])
            success = self.delete_cron_job(job_index)
            
            self._send_headers(200 if success else 500)
            self.wfile.write(json.dumps({'success': success}).encode())

    def get_cron_jobs(self):
        try:
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, check=True)
            jobs = []
            comment = ""
            job_index = 0
            
            for line in result.stdout.split('\n'):
                line = line.strip()
                if not line:
                    comment = ""
                    continue
                elif line.startswith('#'):
                    comment = line[1:].strip()
                elif line and not line.startswith('#'):
                    parts = line.split()
                    if len(parts) >= 5:
                        schedule = ' '.join(parts[:5])
                        command = ' '.join(parts[5:])
                        
                        preview = CronPreview.parse_cron(schedule)
                        
                        jobs.append({
                            'index': job_index,
                            'schedule': schedule,
                            'command': command,
                            'comment': comment or 'Custom cron job',
                            'full_line': line,
                            'description': preview['description'],
                            'next_runs': preview['next_runs'][:3]
                        })
                        job_index += 1
                    comment = ""
            
            return jobs
        except subprocess.CalledProcessError:
            return []

    def add_cron_job(self, schedule, command, comment):
        try:
            current_jobs = []
            try:
                result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, check=True)
                current_jobs = result.stdout.strip().split('\n')
            except subprocess.CalledProcessError:
                pass
            
            if comment:
                current_jobs.append(f"#{comment}")
            current_jobs.append(f"{schedule} {command}")
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.cron') as f:
                f.write('\n'.join(current_jobs) + '\n')
                temp_file = f.name
            
            subprocess.run(['crontab', temp_file], check=True)
            os.unlink(temp_file)
            return True
            
        except Exception as e:
            print(f"Error adding cron job: {e}")
            return False

    def delete_cron_job(self, job_index):
        try:
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split('\n')
            
            filtered_lines = []
            current_job_index = 0
            
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith('#'):
                    if current_job_index == job_index:
                        if i > 0 and lines[i-1].strip().startswith('#'):
                            filtered_lines = filtered_lines[:-1]
                        current_job_index += 1
                        continue
                    current_job_index += 1
                
                filtered_lines.append(line)
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.cron') as f:
                f.write('\n'.join(filtered_lines) + '\n')
                temp_file = f.name
            
            subprocess.run(['crontab', temp_file], check=True)
            os.unlink(temp_file)
            return True
            
        except Exception as e:
            print(f"Error deleting cron job: {e}")
            return False

    def get_cron_activity(self):
        try:
            commands = [
                ['journalctl', '-u', 'cron', '-n', '20', '--no-pager'],
                ['tail', '-20', '/var/log/cron.log'],
                ['tail', '-20', '/var/log/syslog']
            ]
            
            for cmd in commands:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    lines = [line for line in result.stdout.split('\n') if 'CRON' in line][-15:]
                    if lines:
                        return lines
                except subprocess.CalledProcessError:
                    continue
            
            return ["No cron activity found in logs"]
        except Exception:
            return ["Error reading cron logs"]

    def get_dashboard_html(self):
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pi Cron Monitor</title>
    <style>
        :root {
            --primary-color: #007AFF;
            --secondary-color: #5856D6;
            --success-color: #34C759;
            --warning-color: #FF9500;
            --danger-color: #FF3B30;
            --background: #F2F2F7;
            --surface: #FFFFFF;
            --surface-secondary: #F2F2F7;
            --text-primary: #000000;
            --text-secondary: #8E8E93;
            --border-color: #C6C6C8;
            --shadow: 0 1px 3px rgba(0,0,0,0.1);
            --shadow-large: 0 4px 16px rgba(0,0,0,0.1);
            --border-radius: 12px;
            --border-radius-large: 16px;
            --transition: all 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }

        * { 
            box-sizing: border-box; margin: 0; padding: 0;
            -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
        }

        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', sans-serif;
            background: var(--background); color: var(--text-primary); line-height: 1.5;
            font-size: 16px; overflow-x: hidden;
        }

        .container { 
            max-width: 1200px; margin: 0 auto; padding: 20px;
            min-height: 100vh;
        }

        .header {
            text-align: center; margin-bottom: 32px;
            animation: slideDown 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }

        .header h1 { 
            font-size: 2.5rem; font-weight: 700; margin-bottom: 8px;
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .header p { 
            font-size: 1.1rem; color: var(--text-secondary); font-weight: 400;
        }

        .stats-bar {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px; margin-bottom: 24px;
        }

        .stat-card {
            background: var(--surface); padding: 20px; border-radius: var(--border-radius);
            box-shadow: var(--shadow); border: 1px solid var(--border-color);
            text-align: center; transition: var(--transition);
        }

        .stat-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-large); }

        .stat-number { 
            font-size: 2rem; font-weight: 700; margin-bottom: 4px;
            color: var(--primary-color);
        }

        .stat-label { 
            font-size: 0.9rem; color: var(--text-secondary); font-weight: 500;
        }

        .card {
            background: var(--surface); border-radius: var(--border-radius-large);
            box-shadow: var(--shadow); border: 1px solid var(--border-color);
            margin-bottom: 24px; overflow: hidden; transition: var(--transition);
            animation: slideUp 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }

        .card-header {
            padding: 24px 24px 0; display: flex; justify-content: space-between;
            align-items: center; border-bottom: none;
        }

        .card-title { 
            font-size: 1.5rem; font-weight: 700; color: var(--text-primary);
            display: flex; align-items: center; gap: 8px;
        }

        .card-content { padding: 24px; }

        .form-section {
            background: var(--surface-secondary); border-radius: var(--border-radius);
            padding: 24px; margin-bottom: 24px; display: none;
            border: 2px solid var(--primary-color); animation: fadeIn 0.3s ease;
        }

        .form-title { 
            font-size: 1.25rem; font-weight: 600; margin-bottom: 20px;
            color: var(--primary-color);
        }

        .form-grid {
            display: grid; grid-template-columns: 1fr 2fr 1fr; gap: 16px;
            margin-bottom: 20px;
        }

        @media (max-width: 768px) { 
            .form-grid { grid-template-columns: 1fr; }
        }

        .form-group { display: flex; flex-direction: column; }

        .form-label { 
            font-weight: 600; margin-bottom: 6px; color: var(--text-primary);
            font-size: 0.9rem;
        }

        .form-input {
            padding: 12px 16px; border: 1.5px solid var(--border-color); 
            border-radius: 10px; font-size: 1rem; transition: var(--transition);
            background: var(--surface); font-family: 'SF Mono', Monaco, monospace;
        }

        .form-input:focus { 
            outline: none; border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.1);
        }

        .cron-preview {
            background: var(--surface); border: 1.5px solid var(--success-color);
            border-radius: var(--border-radius); padding: 20px; margin-top: 16px;
            display: none; animation: slideDown 0.3s ease;
        }

        .cron-preview.invalid { border-color: var(--danger-color); }

        .preview-title { 
            font-weight: 700; margin-bottom: 12px; color: var(--success-color);
            display: flex; align-items: center; gap: 6px;
        }

        .cron-preview.invalid .preview-title { color: var(--danger-color); }

        .preview-description { 
            font-size: 1.1rem; font-weight: 600; margin-bottom: 8px;
            color: var(--text-primary);
        }

        .preview-explanation { 
            font-size: 0.95rem; color: var(--text-secondary); margin-bottom: 12px;
        }

        .preview-breakdown {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 8px; margin-bottom: 12px;
        }

        .breakdown-item {
            background: var(--surface-secondary); padding: 8px; border-radius: 8px;
            text-align: center; font-size: 0.8rem;
        }

        .breakdown-label { font-weight: 600; color: var(--text-secondary); }
        .breakdown-value { color: var(--text-primary); margin-top: 2px; }

        .preview-next-runs { 
            font-size: 0.9rem; color: var(--text-secondary);
            background: var(--surface-secondary); padding: 12px; border-radius: 8px;
        }

        .btn {
            padding: 12px 20px; border: none; border-radius: 10px; cursor: pointer;
            font-size: 1rem; font-weight: 600; transition: var(--transition);
            text-decoration: none; display: inline-block; text-align: center;
            font-family: inherit;
        }

        .btn-primary { 
            background: var(--primary-color); color: white;
        }
        .btn-primary:hover { 
            background: #0056D2; transform: translateY(-1px);
        }

        .btn-secondary { 
            background: var(--text-secondary); color: white;
        }
        .btn-secondary:hover { background: #6D6D72; }

        .btn-danger { 
            background: var(--danger-color); color: white;
        }
        .btn-danger:hover { 
            background: #D70015; transform: translateY(-1px);
        }

        .btn-success { 
            background: var(--success-color); color: white;
        }
        .btn-success:hover { background: #248A3D; }

        .cron-job {
            background: var(--surface); border: 1px solid var(--border-color);
            border-radius: var(--border-radius); padding: 20px; margin: 12px 0;
            border-left: 4px solid var(--success-color); transition: var(--transition);
        }

        .cron-job:hover { 
            transform: translateY(-2px); box-shadow: var(--shadow-large);
        }

        .job-header {
            display: flex; justify-content: space-between; align-items: flex-start;
            margin-bottom: 16px;
        }

        .job-title { 
            font-size: 1.2rem; font-weight: 700; color: var(--primary-color);
            margin-bottom: 4px;
        }

        .job-description { 
            font-size: 1rem; color: var(--text-secondary); margin-bottom: 12px;
        }

        .job-details {
            display: grid; grid-template-columns: 1fr 2fr; gap: 12px;
            margin-bottom: 12px;
        }

        .job-schedule {
            font-family: 'SF Mono', Monaco, monospace; font-size: 0.9rem;
            background: var(--surface-secondary); padding: 8px 12px;
            border-radius: 8px; color: var(--text-primary); font-weight: 600;
        }

        .job-command {
            font-family: 'SF Mono', Monaco, monospace; font-size: 0.9rem;
            background: var(--surface-secondary); padding: 8px 12px;
            border-radius: 8px; color: var(--text-primary); word-break: break-all;
        }

        .job-next-runs {
            font-size: 0.85rem; color: var(--text-secondary);
            background: rgba(255, 193, 7, 0.1); padding: 8px 12px;
            border-radius: 8px; margin-bottom: 12px;
        }

        .activity-log {
            background: #1C1C1E; color: #00FF41; padding: 20px;
            border-radius: var(--border-radius); font-family: 'SF Mono', Monaco, monospace;
            font-size: 0.85rem; line-height: 1.6; max-height: 400px; overflow-y: auto;
        }

        .activity-log::-webkit-scrollbar { width: 8px; }
        .activity-log::-webkit-scrollbar-track { background: #2C2C2E; }
        .activity-log::-webkit-scrollbar-thumb { background: #48484A; border-radius: 4px; }

        .empty-state {
            text-align: center; padding: 48px; color: var(--text-secondary);
            background: var(--surface-secondary); border-radius: var(--border-radius);
        }

        .empty-icon { font-size: 3rem; margin-bottom: 16px; }

        .progress-bar {
            position: fixed; top: 0; left: 0; width: 100%; height: 3px; z-index: 1000;
            background: rgba(0, 122, 255, 0.1);
        }

        .progress-fill {
            height: 100%; background: linear-gradient(90deg, var(--success-color), var(--primary-color));
            width: 0%; transition: width 0.1s linear;
        }

        .status-indicator {
            display: inline-block; width: 8px; height: 8px; border-radius: 50%;
            background: var(--success-color); margin-right: 6px;
            animation: pulse 2s infinite;
        }

        @keyframes slideDown {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .updating { opacity: 0.8; transition: opacity 0.3s ease; }

        @media (max-width: 768px) {
            .container { padding: 16px; }
            .header h1 { font-size: 2rem; }
            .job-details { grid-template-columns: 1fr; }
            .stats-bar { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="progress-bar">
        <div class="progress-fill" id="progressBar"></div>
    </div>

    <div class="container">
        <div class="header">
            <h1>Pi Cron Monitor</h1>
            <p>Modern cron job management with live preview</p>
        </div>

        <div class="stats-bar">
            <div class="stat-card">
                <div class="stat-number" id="jobCount">0</div>
                <div class="stat-label">Active Jobs</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="activityCount">0</div>
                <div class="stat-label">Recent Events</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="refreshCounter">10</div>
                <div class="stat-label">Next Refresh (s)</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">
                    <span class="status-indicator"></span>Online
                </div>
                <div class="stat-label">System Status</div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h2 class="card-title">📋 Cron Jobs</h2>
                <button class="btn btn-primary" onclick="toggleAddForm()">
                    + Add New Job
                </button>
            </div>
            <div class="card-content">
                <div class="form-section" id="addJobForm">
                    <h3 class="form-title">Add New Cron Job</h3>
                    <form id="cronForm">
                        <div class="form-grid">
                            <div class="form-group">
                                <label class="form-label">Schedule</label>
                                <input type="text" class="form-input" id="cronSchedule" 
                                       placeholder="* * * * *" value="* * * * *" required>
                                <small style="color: var(--text-secondary); margin-top: 4px;">
                                    Format: minute hour day month weekday
                                </small>
                            </div>
                            <div class="form-group">
                                <label class="form-label">Command</label>
                                <input type="text" class="form-input" id="cronCommand" 
                                       placeholder="/path/to/script.sh" required>
                            </div>
                            <div class="form-group">
                                <label class="form-label">Description</label>
                                <input type="text" class="form-input" id="cronComment" 
                                       placeholder="Daily backup task">
                            </div>
                        </div>
                        
                        <div class="cron-preview" id="cronPreview">
                            <div class="preview-title" id="previewTitle">
                                ✅ Schedule Preview
                            </div>
                            <div class="preview-description" id="previewDescription"></div>
                            <div class="preview-explanation" id="previewExplanation"></div>
                            
                            <div class="preview-breakdown" id="previewBreakdown"></div>
                            
                            <div class="preview-next-runs" id="previewNextRuns"></div>
                        </div>
                        
                        <div style="margin-top: 20px;">
                            <button type="submit" class="btn btn-success">Add Cron Job</button>
                            <button type="button" class="btn btn-secondary" onclick="toggleAddForm()" 
                                    style="margin-left: 12px;">Cancel</button>
                        </div>
                    </form>
                </div>
                
                <div id="cronJobsList">
                    <div class="empty-state">
                        <div class="empty-icon">⏰</div>
                        <div><strong>Loading cron jobs...</strong></div>
                    </div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h2 class="card-title">📈 Recent Activity</h2>
            </div>
            <div class="card-content">
                <div class="activity-log" id="activityLog">
                    <div style="color: #8E8E93;">Loading recent activity...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let refreshInterval;
        let countdown = 10;
        let previewTimeout;
        
        // Apple-style smooth animations
        function animateValue(element, start, end, duration, callback) {
            const startTime = performance.now();
            const animate = (currentTime) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const easeProgress = 1 - Math.pow(1 - progress, 3); // Ease out cubic
                
                const current = start + (end - start) * easeProgress;
                callback(current);
                
                if (progress < 1) {
                    requestAnimationFrame(animate);
                }
            };
            requestAnimationFrame(animate);
        }
        
        function startCountdown() {
            countdown = 10;
            const progressBar = document.getElementById('progressBar');
            const counter = document.getElementById('refreshCounter');
            
            const countdownInterval = setInterval(() => {
                countdown--;
                const progress = ((10 - countdown) / 10) * 100;
                
                animateValue(progressBar, parseFloat(progressBar.style.width) || 0, progress, 100, 
                    (value) => progressBar.style.width = value + '%');
                
                counter.textContent = countdown;
                
                if (countdown <= 0) {
                    clearInterval(countdownInterval);
                    setTimeout(() => {
                        progressBar.style.width = '0%';
                    }, 300);
                }
            }, 1000);
        }
        
        async function updateCronPreview() {
            const schedule = document.getElementById('cronSchedule').value.trim();
            const preview = document.getElementById('cronPreview');
            
            if (!schedule) {
                preview.style.display = 'none';
                return;
            }
            
            try {
                const response = await fetch(`/api/preview/${encodeURIComponent(schedule)}`);
                const data = await response.json();
                
                preview.style.display = 'block';
                preview.className = 'cron-preview ' + (data.valid ? '' : 'invalid');
                
                document.getElementById('previewTitle').innerHTML = 
                    data.valid ? '✅ Schedule Preview' : '❌ Invalid Expression';
                
                document.getElementById('previewDescription').textContent = data.description;
                document.getElementById('previewExplanation').textContent = data.explanation;
                
                // Show breakdown
                const breakdown = document.getElementById('previewBreakdown');
                if (data.breakdown) {
                    breakdown.innerHTML = Object.entries(data.breakdown).map(([key, value]) => `
                        <div class="breakdown-item">
                            <div class="breakdown-label">${key}</div>
                            <div class="breakdown-value">${value}</div>
                        </div>
                    `).join('');
                }
                
                // Show next runs
                const nextRuns = document.getElementById('previewNextRuns');
                if (data.next_runs && data.next_runs.length > 0) {
                    nextRuns.innerHTML = `<strong>Next runs:</strong><br>${data.next_runs.join('<br>')}`;
                } else {
                    nextRuns.innerHTML = '<strong>Unable to calculate next runs</strong>';
                }
                
            } catch (error) {
                preview.style.display = 'none';
            }
        }
        
        // Real-time preview with Apple-style responsiveness
        document.getElementById('cronSchedule').addEventListener('input', () => {
            clearTimeout(previewTimeout);
            previewTimeout = setTimeout(updateCronPreview, 150); // Faster response
        });
        
        async function loadCronJobs() {
            try {
                const response = await fetch('/api/jobs');
                const jobs = await response.json();
                const container = document.getElementById('cronJobsList');
                document.getElementById('jobCount').textContent = jobs.length;
                
                if (jobs.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-icon">📝</div>
                            <div><strong>No cron jobs found</strong></div>
                            <div style="margin-top: 8px;">Add jobs using the form above or <code>crontab -e</code></div>
                        </div>
                    `;
                    return;
                }
                
                container.innerHTML = jobs.map(job => `
                    <div class="cron-job">
                        <div class="job-header">
                            <div>
                                <div class="job-title">${job.comment}</div>
                                <div class="job-description">${job.description}</div>
                            </div>
                            <button class="btn btn-danger" onclick="deleteCronJob(${job.index})" 
                                    title="Delete job">Delete</button>
                        </div>
                        <div class="job-details">
                            <div class="job-schedule">${job.schedule}</div>
                            <div class="job-command">${job.command}</div>
                        </div>
                        <div class="job-next-runs">
                            <strong>Next runs:</strong> ${job.next_runs.join(', ') || 'Unable to calculate'}
                        </div>
                    </div>
                `).join('');
                
            } catch (error) {
                console.error('Error loading cron jobs:', error);
            }
        }
        
        async function loadActivity() {
            try {
                const response = await fetch('/api/activity');
                const activity = await response.json();
                const logElement = document.getElementById('activityLog');
                document.getElementById('activityCount').textContent = activity.length;
                
                if (activity.length === 0 || activity[0].includes('No cron activity')) {
                    logElement.innerHTML = '<div style="color: #8E8E93;">No recent cron activity found</div>';
                    return;
                }
                
                logElement.innerHTML = activity.slice(-20).map(line => {
                    if (line.includes('CMD')) {
                        return `<div style="color: #34C759;">→ ${line}</div>`;
                    } else if (line.includes('RELOAD')) {
                        return `<div style="color: #007AFF;">⟲ ${line}</div>`;
                    } else {
                        return `<div style="color: #FF9500;">• ${line}</div>`;
                    }
                }).join('');
                
            } catch (error) {
                console.error('Error loading activity:', error);
            }
        }
        
        async function refreshData() {
            document.querySelector('.container').classList.add('updating');
            
            await Promise.all([
                loadCronJobs(),
                loadActivity()
            ]);
            
            setTimeout(() => {
                document.querySelector('.container').classList.remove('updating');
            }, 200);
        }
        
        function toggleAddForm() {
            const form = document.getElementById('addJobForm');
            const isVisible = form.style.display !== 'none';
            
            form.style.display = isVisible ? 'none' : 'block';
            
            if (!isVisible) {
                document.getElementById('cronSchedule').focus();
                updateCronPreview(); // Show initial preview
            }
        }
        
        async function deleteCronJob(jobIndex) {
            if (!confirm('Are you sure you want to delete this cron job?')) {
                return;
            }
            
            try {
                const response = await fetch(`/api/jobs/${jobIndex}`, {
                    method: 'DELETE'
                });
                
                const result = await response.json();
                
                if (result.success) {
                    refreshData();
                } else {
                    alert('Failed to delete cron job.');
                }
            } catch (error) {
                console.error('Error deleting cron job:', error);
                alert('Error deleting cron job.');
            }
        }
        
        document.getElementById('cronForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const schedule = document.getElementById('cronSchedule').value;
            const command = document.getElementById('cronCommand').value;
            const comment = document.getElementById('cronComment').value;
            
            try {
                const response = await fetch('/api/jobs/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ schedule, command, comment })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    toggleAddForm();
                    document.getElementById('cronForm').reset();
                    document.getElementById('cronSchedule').value = '* * * * *'; // Reset to default
                    document.getElementById('cronPreview').style.display = 'none';
                    refreshData();
                } else {
                    alert('Failed to add cron job. Please check your input.');
                }
            } catch (error) {
                console.error('Error adding cron job:', error);
                alert('Error adding cron job.');
            }
        });
        
        function startAutoRefresh() {
            refreshData();
            startCountdown();
            
            refreshInterval = setInterval(() => {
                refreshData();
                startCountdown();
            }, 10000);
        }
        
        // Tab visibility optimization
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                clearInterval(refreshInterval);
            } else {
                startAutoRefresh();
            }
        });
        
        // Initialize
        startAutoRefresh();
        updateCronPreview(); // Show initial preview for default value
        
        // Cleanup
        window.addEventListener('beforeunload', () => {
            clearInterval(refreshInterval);
            clearTimeout(previewTimeout);
        });
    </script>
</body>
</html>'''

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8088), CronMonitorServer)
    print("🍎 Apple-Style Pi Cron Monitor running at http://localhost:8088")
    print("   Optimized for performance with live cron preview")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  Server stopped")
