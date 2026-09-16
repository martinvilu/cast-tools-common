# cast-tools-common

Biblioteca transversal compartida para las herramientas de control y telemetría de WebExtensions (`meet-tools` y `slide-tools`).

## Módulos incluidos

- `discovery`: Obtención de IP local, generación de URIs de emparejamiento, renderizado QR (ASCII y SVG) y publicación de servicios mDNS/DNS-SD (`MdnsPublisher`).
- `packer`: Empaquetado parametrizado para distribución en Chrome (.zip con Service Worker) y Firefox (.xpi/.zip con Background Scripts y Gecko ID).
- `signer`: Staging, validación sintáctica (`web-ext lint`) y firma digital en Mozilla Add-ons (`web-ext sign`).

## Licencia

GPL-3.0-or-later.
