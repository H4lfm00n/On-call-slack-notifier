#!/usr/bin/env python3
"""
Simple web dashboard for monitoring the on-call buzzer.
Run with: python -m src.dashboard
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from flask import Flask, render_template_string, jsonify, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
STATS_FILE = os.getenv("STATS_FILE", "alert_stats.json")

# HTML template for the dashboard
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>On-Call Buzzer Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 20px; background: #f5f5f5; 
        }
        .container { 
            max-width: 800px; margin: 0 auto; background: white; 
            border-radius: 12px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { color: #333; margin-bottom: 30px; text-align: center; }
        .stats-grid { 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 20px; margin-bottom: 30px; 
        }
        .stat-card { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 20px; border-radius: 8px; text-align: center;
        }
        .stat-number { font-size: 2em; font-weight: bold; margin-bottom: 5px; }
        .stat-label { font-size: 0.9em; opacity: 0.9; }
        .status { 
            padding: 15px; border-radius: 8px; margin-bottom: 20px;
            background: #e8f5e8; border-left: 4px solid #4caf50;
        }
        .config-section { 
            background: #f8f9fa; padding: 20px; border-radius: 8px; 
            margin-bottom: 20px; 
        }
        .config-item { 
            display: flex; justify-content: space-between; 
            margin-bottom: 10px; padding: 8px 0; 
        }
        .refresh-btn { 
            background: #007bff; color: white; border: none; 
            padding: 10px 20px; border-radius: 5px; cursor: pointer;
            font-size: 14px; margin: 10px 5px;
        }
        .refresh-btn:hover { background: #0056b3; }
        .auto-refresh { 
            background: #28a745; 
        }
        .auto-refresh:hover { background: #1e7e34; }
        .auto-refresh.active { background: #dc3545; }
        .auto-refresh.active:hover { background: #c82333; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚨 On-Call Buzzer Dashboard</h1>
        
        <div class="status">
            <strong>Status:</strong> <span id="status">Loading...</span>
            <br><small>Last updated: <span id="last-updated">-</span></small>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number" id="total-alerts">-</div>
                <div class="stat-label">Total Alerts</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="today-alerts">-</div>
                <div class="stat-label">Today's Alerts</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="last-alert">-</div>
                <div class="stat-label">Last Alert</div>
            </div>
        </div>

        <div class="config-section">
            <h3>Configuration</h3>
            <div class="config-item">
                <span>Keywords:</span>
                <span id="keywords">-</span>
            </div>
            <div class="config-item">
                <span>Sound:</span>
                <span id="sound">-</span>
            </div>
            <div class="config-item">
                <span>Rate Limit:</span>
                <span id="rate-limit">-</span>
            </div>
            <div class="config-item">
                <span>Channels:</span>
                <span id="channels">-</span>
            </div>
        </div>

        <div style="text-align: center;">
            <button class="refresh-btn" onclick="refreshData()">🔄 Refresh</button>
            <button class="refresh-btn auto-refresh" id="auto-refresh" onclick="toggleAutoRefresh()">⏰ Auto Refresh</button>
        </div>
    </div>

    <script>
        let autoRefreshInterval = null;
        
        function updateDashboard(data) {
            document.getElementById('total-alerts').textContent = data.stats.total_alerts || 0;
            document.getElementById('today-alerts').textContent = data.stats.alerts_today || 0;
            document.getElementById('last-alert').textContent = data.stats.last_alert_time || 'Never';
            document.getElementById('keywords').textContent = data.config.keywords || '-';
            document.getElementById('sound').textContent = data.config.sound || '-';
            document.getElementById('rate-limit').textContent = data.config.rate_limit || '-';
            document.getElementById('channels').textContent = data.config.channels || '-';
            document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();
            document.getElementById('status').textContent = 'Connected';
        }
        
        function refreshData() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => updateDashboard(data))
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('status').textContent = 'Error loading data';
                });
        }
        
        function toggleAutoRefresh() {
            const btn = document.getElementById('auto-refresh');
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
                btn.textContent = '⏰ Auto Refresh';
                btn.classList.remove('active');
            } else {
                autoRefreshInterval = setInterval(refreshData, 5000);
                btn.textContent = '⏹️ Stop Auto';
                btn.classList.add('active');
            }
        }
        
        // Initial load
        refreshData();
    </script>
</body>
</html>
"""


def load_stats() -> Dict[str, Any]:
    """Load statistics from file."""
    if not Path(STATS_FILE).exists():
        return {
            "total_alerts": 0,
            "alerts_today": 0,
            "last_alert_time": None,
            "last_reset_date": ""
        }
    
    try:
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {
            "total_alerts": 0,
            "alerts_today": 0,
            "last_alert_time": None,
            "last_reset_date": ""
        }


def get_config() -> Dict[str, Any]:
    """Get current configuration."""
    return {
        "keywords": os.getenv("KEYWORDS", "@help, help me, urgent"),
        "sound": Path(os.getenv("SOUND_PATH", "/System/Library/Sounds/Submarine.aiff")).stem,
        "rate_limit": f"{os.getenv('RATE_LIMIT_MINUTES', '5')} minutes",
        "channels": os.getenv("CHANNEL_ALLOWLIST", "All channels") or "All channels"
    }


@app.route('/')
def dashboard():
    """Main dashboard page."""
    return render_template_string(DASHBOARD_TEMPLATE)


@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics."""
    return jsonify({
        "stats": load_stats(),
        "config": get_config(),
        "timestamp": datetime.now().isoformat()
    })


if __name__ == '__main__':
    print("🌐 Starting On-Call Buzzer Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:5000")
    print("🔄 Press Ctrl+C to stop")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
