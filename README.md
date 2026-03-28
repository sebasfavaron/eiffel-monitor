# Eiffel Tower Monitor

Monitor de disponibilidad de entradas para la Torre Eiffel (summit, 2 personas, 15-19 mayo 2026).

## Setup en RPi

```bash
# 1. Copiar archivos
cd ~
mkdir eiffel-monitor
# Copiar monitor.py, requirements.txt a ~/eiffel-monitor/

# 2. Instalar dependencias
sudo apt update
sudo apt install -y python3-pip
pip3 install -r requirements.txt
playwright install chromium

# 3. Instalar servicio
sudo cp eiffel-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable eiffel-monitor
sudo systemctl start eiffel-monitor

# 4. Ver logs
journalctl -u eiffel-monitor -f
```

## Configuración

- Fechas objetivo: 15-19 mayo 2026
- Tipo: summit (cima)
- Personas: 2
- Intervalo: 15 min
- Notificación: Telegram

## Archivos

- `monitor.py` - Script principal
- `requirements.txt` - Dependencias
- `eiffel-monitor.service` - Servicio systemd
- `monitor.log` - Logs del monitor
- `state.json` - Estado de alertas enviadas
