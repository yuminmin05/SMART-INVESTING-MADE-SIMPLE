#!/usr/bin/env python
"""จุดเริ่มต้นสำหรับคำสั่งจัดการ Django"""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_dca.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
