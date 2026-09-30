# cast-tools-common

Biblioteca transversal compartida para las herramientas de control y telemetría de WebExtensions (`meet-tools` y `slide-tools`).

No tiene ejecutables: se usa como dependencia. meet-tools y slide-tools la declaran como
referencia git fijada (nunca por nombre en PyPI):

```toml
dependencies = [
    "cast-tools-common @ git+https://github.com/martinvilu/cast-tools-common@<commit>",
]
```

## Módulos incluidos

- `discovery`: Obtención de IP local, generación de URIs de emparejamiento, renderizado QR (ASCII y SVG) y publicación de servicios mDNS/DNS-SD (`MdnsPublisher`).
- `packer`: Empaquetado parametrizado para distribución en Chrome (.zip con Service Worker) y Firefox (.xpi/.zip con Background Scripts y Gecko ID).
- `signer`: Staging, validación sintáctica (`web-ext lint`) y firma digital en Mozilla Add-ons (`web-ext sign`).

## API

Todo lo público se importa desde el paquete: `from cast_tools_common import …`.

### Descubrimiento y emparejamiento (`discovery`)

| Función | Qué hace |
|:--|:--|
| `get_local_ip() -> str` | IP de la interfaz de red principal; `127.0.0.1` si no hay red. |
| `build_pairing_uri(service, host, port, pin, name=None) -> str` | URI de emparejamiento `bridge://pair?v=1.3&host=…&port=…&service=…&pin=…&name=…` (`name`, por omisión, el nombre del equipo). |
| `generate_qr_ascii(data) -> str` | Código QR para mostrar en la terminal. |
| `generate_qr_svg(data) -> str` | Código QR como SVG. |
| `MdnsPublisher(service_name, service_type, port, properties=None, host_ip=None)` | Publica el servicio en la red local con mDNS/DNS-SD. `await start()` devuelve `False` (y libera todo) si la red no permite multicast: la herramienta sigue en modo directo. `await stop()` lo da de baja. |

```python
from cast_tools_common import MdnsPublisher, build_pairing_uri, generate_qr_ascii, get_local_ip

uri = build_pairing_uri("meet", get_local_ip(), 8765, pin="123456")
print(generate_qr_ascii(uri))
publicador = MdnsPublisher("aula-1", "_meet._tcp.local", 8765, {"v": "1"})
publicado = await publicador.start()
```

### Empaquetado (`packer`)

`pack_web_extension(extension_dir, output_dir=None, target="both", addon_id="bridge@local.dev", addon_slug="bridge", firefox_background_scripts=True) -> dict[str, Path]`

Genera `<slug>-chrome-v<versión>.zip` (manifiesto con `service_worker`) y
`<slug>-firefox-v<versión>.xpi` (con `background.scripts` y el `gecko.id`), según `target`
(`"chrome"`, `"firefox"` o `"both"`). Omite los archivos ocultos. Sin `manifest.json` lanza
`FileNotFoundError`.

### Validación y firma (`signer`)

| Función | Qué hace |
|:--|:--|
| `prepare_firefox_staging(extension_dir, staging_dir, addon_id=…, firefox_background_scripts=False) -> Path` | Copia la extensión (sin ocultos ni temporales) y adapta el manifiesto a las reglas de firma de Mozilla. |
| `run_web_ext_lint(source_dir) -> tuple[bool, str]` | `web-ext lint` sobre la carpeta preparada. |
| `sign_firefox_addon(extension_dir, output_dir=None, api_key=None, api_secret=None, channel="unlisted", …, lint_only=False, dry_run=False) -> dict` | Staging, lint y `web-ext sign`. Devuelve `status` = `signed` (con `signed_file`), `lint_passed`/`lint_failed` (con `lint_only`) o `dry_run` (con el comando que ejecutaría). |

Las credenciales de Mozilla AMO se pasan como argumentos o por las variables de entorno
`WEB_EXT_API_KEY` y `WEB_EXT_API_SECRET` (también `AMO_JWT_ISSUER`/`AMO_JWT_SECRET`). Errores:
`RuntimeError` si falla el lint o la firma, `ValueError` si faltan credenciales y
`FileNotFoundError` si la firma no produjo el `.xpi`.

Requiere [`web-ext`](https://extensionworkshop.com/documentation/develop/getting-started-with-web-ext/)
(`npm install --global web-ext`) para lint y firma; el empaquetado no lo necesita.

## Licencia

GPL-3.0-or-later.
