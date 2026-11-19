"""Exact channel-reference substitutions for the explicitly requested CX copy."""
import re

MODULES = {
    'B2C_SYSTEM': 'CX_COMMS_SYSTEM',
    'B2C_TEMPLATES': 'CX_COMMS_TEMPLATES',
    'B2C_USER_GUIDE': 'CX_COMMS_USER_GUIDE',
}


def cx_comms_copy(content):
    # Keep machine-readable IDs/anchors valid while renaming human labels.
    text = content.replace('B2C_', 'CX_COMMS_').replace('b2c_', 'cx_comms_')
    text = text.replace('B2C-', 'CX-COMMS-').replace('b2c-', 'cx-comms-')
    text = text.replace('/b2c', '/cx-comms')
    text = re.sub(r'\bb2c\b', 'cx-comms', text)
    return re.sub(r'\bb2c\b', 'CX Comms', text, flags=re.I)
