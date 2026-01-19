#!/bin/bash
# FML Dashboard Startup Script

cd /Users/johnkennedy/DevelopmentArea/Firebolt-Memory-Layer/fml/dashboard

# Ensure PATH includes homebrew
export PATH="/opt/homebrew/bin:$PATH"

# Start the Vite dev server
exec /opt/homebrew/bin/npm run dev -- --host
