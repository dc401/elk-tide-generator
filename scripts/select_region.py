#!/usr/bin/env python3
"""select GCP region using round-robin rotation based on timestamp

rotates through multiple regions to distribute API quota usage
uses current hour of day for deterministic selection (no state needed)
supports retry offset for quota exhaustion recovery
"""
import sys
from datetime import datetime

#available Gemini API regions (all support Vertex AI)
REGIONS = [
    'us-central1',
    'global',
    'us-south1',
    'us-east5',
    'us-west1',
    'us-east1',
    'us-east4',
    'us-west4',
]

def select_region(retry_offset=0):
    """select region based on current hour + retry offset

    Args:
        retry_offset: number of retries (shifts to next region in list)
                     0 = normal selection (hour-based)
                     1 = next region after normal
                     2 = region after that, etc.
    """
    current_hour = datetime.utcnow().hour
    #add retry offset to shift to next region
    region_index = (current_hour + retry_offset) % len(REGIONS)
    selected_region = REGIONS[region_index]

    if retry_offset > 0:
        print(f"Region retry {retry_offset}: Hour {current_hour} UTC + offset {retry_offset} → {selected_region}", file=sys.stderr)
    else:
        print(f"Region rotation: Hour {current_hour} UTC → {selected_region}", file=sys.stderr)

    print(f"Available regions: {', '.join(REGIONS)}", file=sys.stderr)
    print(selected_region)  #stdout for GitHub Actions capture

    return selected_region

if __name__ == '__main__':
    #optional: pass retry_offset as first argument
    retry_offset = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    select_region(retry_offset)
