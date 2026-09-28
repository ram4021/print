# QR Print System

QR Scan → Document → Print Agent → Canon printer.

## Architecture

Mobile QR scan → Flask web server → print queue → Windows Print Agent → Canon 3010.

## Components

- `server/` — Flask web application
- `print-agent/` — Windows print agent

## Security

Keep the agent token secret. Do not commit real credentials or production secrets.
