#!/usr/bin/env python3
"""
Startup script for the AI Voice Interview Agent FastAPI server
"""

import uvicorn
import os
import sys

def main():
    """Start the FastAPI server"""
    print("🎤 Starting AI Voice Interview Agent Server...")
    print("📁 Project Directory:", os.getcwd())
    
    # Check if static directory exists
    if not os.path.exists("static"):
        print("❌ Error: 'static' directory not found!")
        print("   Make sure you're running this from the project root directory.")
        sys.exit(1)
    
    # Check if static files exist
    required_files = ["static/index.html", "static/styles.css", "static/script.js"]
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Error: Required file '{file}' not found!")
            sys.exit(1)
    
    print("✅ All static files found")
    print("🚀 Starting server on http://localhost:8000")
    print("📱 Open your browser and navigate to: http://localhost:8000")
    print("⏹️  Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
