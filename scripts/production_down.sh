#!/bin/bash
set -e

echo "WARNING: Shutting down PRODUCTION services..."
echo "Press Ctrl+C to cancel"

for i in 5 4 3 2 1; do echo "$i..."; sleep 1; done

railway down --service backend-production --yes
railway down --service frontend-production --yes

echo "Done. Production services stopped."
