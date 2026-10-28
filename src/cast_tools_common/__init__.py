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
from cast_tools_common.reconexion import con_reintentos, esperas
from cast_tools_common.registro import configurar_registro, ruta_registro
from cast_tools_common.seguridad import (
    LimitadorIntentos,
    TokensEfimeros,
    conexion_local_confiable,
    filtro_de_origen,
    generar_pin,
    origen_permitido,
    pin_correcto,
    rechazar_origen_web,
)
from cast_tools_common.signer import (
    prepare_firefox_staging,
    run_web_ext_lint,
    sign_firefox_addon,
)

__all__ = [
    "LimitadorIntentos",
    "MdnsPublisher",
    "TokensEfimeros",
    "con_reintentos",
    "conexion_local_confiable",
    "configurar_registro",
    "esperas",
    "filtro_de_origen",
    "generar_pin",
    "origen_permitido",
    "pin_correcto",
    "rechazar_origen_web",
    "ruta_registro",
    "build_pairing_uri",
    "generate_qr_ascii",
    "generate_qr_svg",
    "get_local_ip",
    "pack_web_extension",
    "prepare_firefox_staging",
    "run_web_ext_lint",
    "sign_firefox_addon",
]
