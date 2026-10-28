# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
versiones según [SemVer](https://semver.org/lang/es/).

## [Sin publicar]

### Agregado

- **seguridad**: PIN con comparación en tiempo constante, tokens de reconexión que vencen, filtro de origen web (403 a los WebSocket abiertos por una página), conexión local confiable y límite de intentos, comunes a meet-tools y slide-tools (Ola 24).
- **reconexion**: espera exponencial con azar para los clientes.
- **registro**: registro rotativo en `~/.local/state/p1/cast.log`.
- **atajos**: atajos de teclado globales en GNOME.
- **bandeja**: indicador de estado en la bandeja del sistema (extra `bandeja`) o notificaciones de escritorio.
- Dependencia `websockets>=13.0`.

## [0.1.1] - 2026-09-28

Primera versión con registro de cambios; lo anterior está en el historial de git.

### Documentación

- agregar el texto de la licencia GPL-3.0-or-later que declara pyproject (N-ECO-06) (`6ab738d`)

### Mantenimiento

- **calidad**: verificar errores de Python y dependencias vulnerables (N-ECO-08, N-ECO-13) (`973072d`)
