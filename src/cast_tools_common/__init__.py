"""cast-tools-common: Biblioteca compartida para herramientas de telemetría y control WebExtensions."""

__version__ = "0.1.1"

from cast_tools_common.discovery import (
    MdnsPublisher,
    build_pairing_uri,
    generate_qr_ascii,
    generate_qr_svg,
    get_local_ip,
)
from cast_tools_common.packer import pack_web_extension
from cast_tools_common.signer import (
    prepare_firefox_staging,
    run_web_ext_lint,
    sign_firefox_addon,
)

__all__ = [
    "MdnsPublisher",
    "build_pairing_uri",
    "generate_qr_ascii",
    "generate_qr_svg",
    "get_local_ip",
    "pack_web_extension",
    "prepare_firefox_staging",
    "run_web_ext_lint",
    "sign_firefox_addon",
]
