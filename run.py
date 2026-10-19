#!/usr/bin/env python3
"""Run this checkout, regardless of shell cwd or other installed versions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
if __name__ == '__main__':
    if len(sys.argv) == 1 or sys.argv[1:] == ['start']:
        from floatland.session import main
        sys.exit(main())
    from floatland.cli import main
    main()
