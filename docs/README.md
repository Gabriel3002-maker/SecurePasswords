# Documentación de SecurePasswords

## Español

SecurePasswords es un gestor de contraseñas web con terminal SSH integrado, bot de Telegram y recuperación por código. En esta versión v1.0.3 se incorpora el asistente de configuración, traducción en vivo (es/en/pt), notificaciones y recuperación por Telegram, y el despliegue con Docker.

### Cambios incluidos en v1.0.3
- Asistente de configuración en 2 pasos: idioma + contraseña maestra; admin + Telegram
- Traducción dinámica español / inglés / portugués
- Contraseña maestra hasheada con bcrypt y recuperable por Telegram
- Bot de Telegram: avisos de inicio de sesión y códigos de recuperación
- Terminal SSH corregido (WebSocket) con limpieza de recursos
- Despliegue con Docker Compose en un solo comando
- 32 pruebas automatizadas en verde

### Próximos pasos
- Pulir aún más la experiencia visual
- Añadir más módulos de gestión
- Mejorar la documentación técnica y el despliegue

## English

SecurePasswords is a web password manager with an integrated SSH terminal, Telegram bot, and code-based recovery. This v1.0.3 release adds the setup wizard, live translation (ES/EN/PT), Telegram notifications and recovery, plus Docker deployment.

### Changes included in v1.0.3
- 2-step setup wizard: language + master password; admin + Telegram
- Dynamic Spanish / English / Portuguese translation
- Master password hashed with bcrypt and recoverable via Telegram
- Telegram bot: login alerts and recovery codes
- Fixed SSH terminal (WebSocket) with resource cleanup
- One-command Docker Compose deployment
- 32 automated tests passing

### Next steps
- Further refinement of the visual experience
- Add more management modules
- Improve technical documentation and deployment
