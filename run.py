#!/usr/bin/env python3
"""Run this checkout, regardless of shell cwd or other installed versions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'qt':
        import runpy
        integration = Path(__file__).resolve().parent / 'integrations/qt/launch.py'
        if not integration.is_file():
            sys.exit('Optional Qt integration is not installed. Normal Floatland remains available.')
        sys.argv = [str(integration)] + sys.argv[2:]
        runpy.run_path(str(integration), run_name='__main__')
        sys.exit(0)
    if len(sys.argv) == 1 or sys.argv[1:] == ['start']:
        from floatland.session import main
        sys.exit(main())
    from floatland.cli import main
    main()
